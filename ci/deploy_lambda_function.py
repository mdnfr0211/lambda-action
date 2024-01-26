import boto3
import json
import os
import concurrent.futures


lambda_client = boto3.client("lambda")

alias = os.getenv("ALIAS_NAME")
artifact_bucket = os.getenv("ARTIFACT_BUCKET")
function_config_file = os.getenv("LAMBDA_CONFIG_FILE")
publish = os.getenv("PUBLISH", "true") == "true"
runner_id = os.getenv("RUNNER_ID")

default_layers = [
    "arn:aws:lambda:ap-southeast-1:044395824272:layer:AWS-Parameters-and-Secrets-Lambda-Extension:5"
]


def read_function_data(file_path):
    with open(file_path, "r") as f:
        return json.load(f)
    

def wait_for_function_update(function_name):
    waiter = lambda_client.get_waiter("function_updated_v2")
    waiter.wait(FunctionName=function_name, WaiterConfig={"Delay": 5})


def update_functions(function):
    function_name = function["function_name"]
    zip_file_name = function["zip_file_name"]

    response = lambda_client.update_function_code(
        FunctionName=function_name,
        S3Bucket=artifact_bucket,
        S3Key=f"function/{runner_id}/{zip_file_name}",
        Publish=publish,
        Architectures=["x86_64"],
    )
    print(f"Updated Function Code for {function_name}")


def update_functions_code(function_data):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = executor.map(update_functions, function_data)


def update_functions_alias(function_data):
    for function in function_data:
        function_name = function["function_name"]
        paginator = lambda_client.get_paginator("list_versions_by_function").paginate(
            FunctionName=function_name
        )
        for i in paginator:
            latest_version = i["Versions"][-1]["Version"]

        response = lambda_client.update_alias(
            FunctionName=function_name,
            Name=alias,
            FunctionVersion=latest_version,
        )
        print(f"Updated Alias for {function_name}")


def get_latest_layer_versions(layer_name):
    response = lambda_client.list_layer_versions(LayerName=layer_name)
    latest_version = max(response["LayerVersions"], key=lambda v: v["Version"])
    return latest_version["LayerVersionArn"]


def update_functions_config(function):
    function_name = function["function_name"]
    layers = function.get("layers", [])
    runtime = function["runtime"]
    handler = function["handler"]

    custom_layers = [get_latest_layer_versions(layer) for layer in layers]

    wait_for_function_update(function_name)

    response = lambda_client.update_function_configuration(
        FunctionName=function_name,
        Layers=custom_layers + default_layers,
        Runtime=runtime,
        Handler=handler
    )
    print(f"Updated Function Configuration for {function_name}")


def update_functions_configuration(function_data):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = executor.map(update_functions_config, function_data)


if __name__ == "__main__":
    function_data = read_function_data(function_config_file)["functions"]

    update_functions_code(function_data)

    if publish:
        update_functions_alias(function_data)

    update_functions_configuration(function_data)