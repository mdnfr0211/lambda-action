# lambda-action

GitHub Action for deploying Lambda code and Updating Configuration to an Existing function

## Usage

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
        env:
          PUBLISH: true
          ALIAS_NAME: dev
          ARTIFACT_BUCKET: <ARTIFACT-BUCKET>
          ARTIFACT_PATH: function/<PATH>
          LAMBDA_CONFIG_FILE: <PATH-OF-JSON-FILE>

```

The Artifact Path is not required to include the zip file, It requires only the Path for the Zip File


## License

[MIT](https://choosealicense.com/licenses/mit/)