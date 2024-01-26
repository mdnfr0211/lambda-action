FROM python:3.10

WORKDIR /app

COPY . .

RUN pip install -r ci/requirements.txt

ENTRYPOINT ["python", "/app/ci/deploy_lambda_function.py"]
