# lambda-action

GitHub Action for deploying Lambda code and updating configuration to existing Lambda functions.

## Features

- ✅ Concurrent function updates for faster deployments
- ✅ Comprehensive error handling with detailed logging
- ✅ Automatic layer version resolution
- ✅ Support for custom architectures (x86_64, arm64)
- ✅ Alias management with version control
- ✅ Graceful failure handling (continues on partial failures)

## Usage

### Configuration File Format

```bash
{
    "functions": [
        {
            "function_name": "test",
            "zip_file_name": "function.zip",
            "runtime": "python3.11",
            "layers": [],
            "extension_layers": [
                "arn:aws:lambda:<your-region>:044395824272:layer:AWS-Parameters-and-Secrets-Lambda-Extension:11"
            ],
            "handler": "app.lambdaHandler"
        },
        {
            "function_name": "test1",
            "zip_file_name": "function1.zip",
            "runtime": "python3.12",
            "layers": [
                "test"
            ],
            "extension_layers": [
                "arn:aws:lambda:<your-region>:634166935893:layer:vault-lambda-extension:13"
            ],
            "handler": "app.lambdaHandler",
            "architecture": "x86_64"
        }
    ],
    "layers": []
}
```

```bash
name: Deploy

on:
  push:
    branches:
      - main

jobs:
  Deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Assume IAM role
        uses: aws-actions/configure-aws-credentials@v3
        with:
          role-to-assume: <ROLE-TO-ASSUME>
          aws-region: <AWS-REGION>
        
      - name: deploy lambda
        uses: mdnfr0211/lambda-action@v4
        with:
          publish: true
          alias_name: dev
          artifact_bucket: <ARTIFACT-BUCKET>
          artifact_path: function/<PATH>
          lambda_config_file: <PATH-OF-JSON-FILE>

```

The Artifact Path is not required to include the zip file, it requires only the path to the directory containing the zip files.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `artifact_bucket` | Yes | - | S3 bucket containing the Lambda deployment packages |
| `artifact_path` | Yes | - | Path within the S3 bucket to the directory containing zip files |
| `lambda_config_file` | Yes | - | Path to the JSON configuration file |
| `publish` | No | `true` | Whether to publish a new version and update alias |
| `alias_name` | Conditional | - | Required if `publish` is `true`. Name of the alias to update |

## Deployment Process

The action performs the following steps in order:

1. **Configuration Update**: Updates function configuration (runtime, handler, layers) for all functions concurrently
2. **Code Update**: Deploys new code from S3 for all functions concurrently
3. **Alias Update**: Updates aliases to point to the new versions (if `PUBLISH=true`)

## Error Handling

- The action uses structured logging with clear success (✓) and failure (✗) indicators
- Partial failures are logged but don't stop the entire deployment
- If all functions fail in any step, the deployment will exit with an error
- Each function's status is tracked and reported individually

## Logging

The action provides concise, informative logging:
- Step-by-step progress indicators
- Individual function status updates
- Summary reports for each deployment phase
- Detailed error messages when failures occur

## License

[MIT](https://choosealicense.com/licenses/mit/)
