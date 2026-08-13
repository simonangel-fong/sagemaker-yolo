```sh
# package the model and upload to S3
python -m deploy.package

# test the endpoint
python -m deploy.invoke --image data/raw/audi_a5_with_license_plate_43.png
python -m deploy.invoke --all-raw --limit 3



terraform -chdir=infra apply -auto-approve
python deploy/lambda/test_local.py
curl https://dj72p18fcw10v.cloudfront.net/v1/models/yolo-car-plate

```
