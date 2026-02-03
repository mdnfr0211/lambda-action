FROM python:3.14-slim

LABEL maintainer="Mohamed Navfar"
LABEL description="Deploy Lambda functions with concurrent updates and comprehensive error handling"

WORKDIR /app

COPY ci/requirements.txt /app/ci/requirements.txt

RUN pip install --no-cache-dir -r ci/requirements.txt

COPY ci/deploy_lambda_function.py /app/ci/deploy_lambda_function.py

ENTRYPOINT ["python", "/app/ci/deploy_lambda_function.py"]
