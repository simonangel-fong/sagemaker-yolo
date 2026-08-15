stage: refactor lambda function

goal:
- convert to docker image, fastapi

steps
1. create fastapi app: lambda/app
2. create dokerfile,`lambda/Dockerfile` build
3. update infra: ecr; push ecr
4. update infra: lambda
5. test