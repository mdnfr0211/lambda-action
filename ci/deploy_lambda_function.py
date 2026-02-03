import boto3
import concurrent.futures
import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

lambda_client = boto3.client("lambda")

alias = os.getenv("ALIAS_NAME")
artifact_bucket = os.getenv("ARTIFACT_BUCKET")
function_config_file = os.getenv("LAMBDA_CONFIG_FILE")
publish = os.getenv("PUBLISH", "true") == "true"
artifact_path = os.getenv("ARTIFACT_PATH")


def read_function_data(file_path):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data.get('functions', []))} functions from config")
        return data
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error reading configuration file: {e}")
        raise


def wait_for_function_update(function_name):
    try:
        waiter = lambda_client.get_waiter("function_updated_v2")
        waiter.wait(FunctionName=function_name, WaiterConfig={"Delay": 5})
    except Exception as e:
        logger.error(f"Error waiting for function {function_name} to be ready: {e}")
        raise


def update_functions(function):
    function_name = function.get("function_name", "UNKNOWN")
    try:
        zip_file_name = function["zip_file_name"]
        architecture = function.get("architecture", "x86_64")

        wait_for_function_update(function_name)

        response = lambda_client.update_function_code(
            FunctionName=function_name,
            S3Bucket=artifact_bucket,
            S3Key=f"{artifact_path}/{zip_file_name}",
            Publish=publish,
            Architectures=[architecture],
        )

        logger.info(f"✓ Updated code: {function_name} (v{response.get('Version', 'N/A')})")
        return {"success": True, "function_name": function_name}
    except KeyError as e:
        logger.error(f"✗ Missing required configuration key for function {function_name}: {e}")
        return {"success": False, "function_name": function_name, "error": str(e)}
    except lambda_client.exceptions.ResourceNotFoundException as e:
        logger.error(f"✗ Function {function_name} not found: {e}")
        return {"success": False, "function_name": function_name, "error": str(e)}
    except Exception as e:
        logger.error(f"✗ Failed to update function code for {function_name}: {e}")
        return {"success": False, "function_name": function_name, "error": str(e)}


def update_functions_code(function_data):
    try:
        results = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_function = {
                executor.submit(update_functions, func): func["function_name"]
                for func in function_data
            }

            for future in concurrent.futures.as_completed(future_to_function):
                function_name = future_to_function[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Exception for {function_name}: {e}")
                    results.append({"success": False, "function_name": function_name, "error": str(e)})

        failed = [r for r in results if not r.get("success")]
        if failed:
            logger.warning(f"Code update: {len(results) - len(failed)}/{len(results)} successful")
            for f in failed:
                logger.warning(f"  ✗ {f['function_name']}: {f.get('error', 'Unknown error')}")
            if len(failed) == len(results):
                raise Exception("All function code updates failed")

    except Exception as e:
        logger.error(f"Error during function code updates: {e}")
        raise


def update_functions_alias(function_data):
    failed_updates = []

    for function in function_data:
        function_name = function.get("function_name", "UNKNOWN")
        try:
            paginator = lambda_client.get_paginator("list_versions_by_function").paginate(
                FunctionName=function_name
            )

            latest_version = None
            for i in paginator:
                latest_version = i["Versions"][-1]["Version"]

            if not latest_version:
                logger.error(f"✗ No versions found: {function_name}")
                failed_updates.append(function_name)
                continue

            wait_for_function_update(function_name)

            lambda_client.update_alias(
                FunctionName=function_name,
                Name=alias,
                FunctionVersion=latest_version,
            )

            logger.info(f"✓ Updated alias: {function_name} -> {alias} (v{latest_version})")
        except lambda_client.exceptions.ResourceNotFoundException:
            logger.error(f"✗ Not found: {function_name}")
            failed_updates.append(function_name)
        except Exception as e:
            logger.error(f"✗ Failed alias update: {function_name} - {e}")
            failed_updates.append(function_name)

    if failed_updates:
        logger.warning(f"Alias update: {len(function_data) - len(failed_updates)}/{len(function_data)} successful")
        if len(failed_updates) == len(function_data):
            raise Exception("All alias updates failed")


def get_latest_layer_versions(layer_name):
    try:
        response = lambda_client.list_layer_versions(LayerName=layer_name)

        if not response.get("LayerVersions"):
            logger.error(f"No versions found for layer: {layer_name}")
            raise Exception(f"No versions found for layer {layer_name}")

        latest_version = max(response["LayerVersions"], key=lambda v: v["Version"])
        return latest_version["LayerVersionArn"]
    except lambda_client.exceptions.ResourceNotFoundException:
        logger.error(f"Layer not found: {layer_name}")
        raise
    except Exception as e:
        logger.error(f"Error fetching layer {layer_name}: {e}")
        raise


def update_functions_config(function):
    function_name = function.get("function_name", "UNKNOWN")
    try:
        layers = function.get("layers", [])
        runtime = function["runtime"]
        handler = function["handler"]
        ext_layers = function.get("extension_layers", [])

        custom_layers = [get_latest_layer_versions(layer) for layer in layers]

        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Layers=custom_layers + ext_layers,
            Runtime=runtime,
            Handler=handler
        )

        logger.info(f"✓ Updated config: {function_name}")
        return {"success": True, "function_name": function_name}
    except KeyError as e:
        logger.error(f"✗ Missing required configuration key for function {function_name}: {e}")
        return {"success": False, "function_name": function_name, "error": str(e)}
    except lambda_client.exceptions.ResourceNotFoundException as e:
        logger.error(f"✗ Function {function_name} not found: {e}")
        return {"success": False, "function_name": function_name, "error": str(e)}
    except Exception as e:
        logger.error(f"✗ Failed to update configuration for {function_name}: {e}")
        return {"success": False, "function_name": function_name, "error": str(e)}


def update_functions_configuration(function_data):
    try:
        results = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_function = {
                executor.submit(update_functions_config, func): func["function_name"]
                for func in function_data
            }

            for future in concurrent.futures.as_completed(future_to_function):
                function_name = future_to_function[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Exception for {function_name}: {e}")
                    results.append({"success": False, "function_name": function_name, "error": str(e)})

        failed = [r for r in results if not r.get("success")]
        if failed:
            logger.warning(f"Config update: {len(results) - len(failed)}/{len(results)} successful")
            for f in failed:
                logger.warning(f"  ✗ {f['function_name']}: {f.get('error', 'Unknown error')}")
            if len(failed) == len(results):
                raise Exception("All function configuration updates failed")

    except Exception as e:
        logger.error(f"Error during function configuration updates: {e}")
        raise


if __name__ == "__main__":
    try:
        logger.info("Starting Lambda deployment")
        logger.info(f"Config: {function_config_file} | Bucket: {artifact_bucket}/{artifact_path}")

        required_vars = {
            "ARTIFACT_BUCKET": artifact_bucket,
            "LAMBDA_CONFIG_FILE": function_config_file,
            "ARTIFACT_PATH": artifact_path
        }

        missing_vars = [k for k, v in required_vars.items() if not v]
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            sys.exit(1)

        if publish and not alias:
            logger.error("ALIAS_NAME is required when PUBLISH is true")
            sys.exit(1)

        function_data = read_function_data(function_config_file)["functions"]

        logger.info("[1/3] Updating function configurations...")
        update_functions_configuration(function_data)

        logger.info("[2/3] Updating function code...")
        update_functions_code(function_data)

        if publish:
            logger.info(f"[3/3] Updating function aliases to '{alias}'...")
            update_functions_alias(function_data)
        else:
            logger.info("[3/3] Skipping alias update (publish=false)")

        logger.info("✓ Deployment completed successfully")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("Deployment interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"✗ Deployment failed: {e}")
        sys.exit(1)
