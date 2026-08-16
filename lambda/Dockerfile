# Dockerfile
#   docker build -t yolo-inference deploy/lambda

FROM public.ecr.aws/lambda/python:3.12

# dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY app/app.py ${LAMBDA_TASK_ROOT}/

# entrypoint: app.py defines `handler = Mangum(app)`
CMD ["app.handler"]