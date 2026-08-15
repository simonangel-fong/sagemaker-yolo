## Promote model

```sh
aws sagemaker update-model-package --model-package-arn arn:aws:sagemaker:ca-central-1:099139718958:model-package/sagemaker-yolo/2 --model-approval-status Approved
# {
    # "ModelPackageArn": "arn:aws:sagemaker:ca-central-1:099139718958:model-package/sagemaker-yolo/2"
# }

```

---

## App

```sh
# the artifact is packaged by the PackageYolo pipeline step, which injects
# code/inference.py from inference/ -- nothing to build locally

# test the endpoint
python -m deploy.invoke --image data/raw/audi_a5_with_license_plate_43.png
python -m deploy.invoke --all-raw --limit 3



terraform -chdir=infra apply -auto-approve
python deploy/lambda/test_local.py
curl https://dj72p18fcw10v.cloudfront.net/v1/models/yolo-car-plate

```
