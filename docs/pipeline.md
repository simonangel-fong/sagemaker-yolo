# Sagemaker yolo - Pipeline

[Back](../README.md)

- [Sagemaker yolo - Pipeline](#sagemaker-yolo---pipeline)
  - [Pipeline](#pipeline)
  - [Debug](#debug)

---

## Pipeline

```sh
# confirm raw data
aws s3 ls s3://sagemaker-yolo-dev-up68ac/raw-data/ --summarize

# get execution role and bucket
terraform -chdir=infra output -raw studio_domain_role_arn
# arn:aws:iam::099139718958:role/sagemaker-yolo-dev-sagemaker-execution-role
terraform -chdir=infra output -raw s3_bucket_name
# sagemaker-yolo-dev-up68ac

# upsert + run the pipeline
cd train/
python pipeline.py --role-arn arn:aws:iam::099139718958:role/sagemaker-yolo-dev-sagemaker-execution-role --bucket sagemaker-yolo-dev-up68ac
```

---

## Debug


```sh
# Check the split
aws s3 ls s3://sagemaker-yolo-dev-up68ac/train-pipeline/split/ --recursive --summarize 

# confirm/data.yaml
aws s3 cp s3://sagemaker-yolo-dev-up68ac/train-pipeline/config/data.yaml -
```

Expected, for 556 pairs at a 0.2 val fraction:

```
train 445, val 111
```

```yaml
path: /opt/ml/input/data/split
train: train/images
val: val/images
nc: 1
names: ['car_plate']
```

Clear the outputs before a re-run, so a stale split cannot be mistaken for a
fresh one.

```sh
aws s3 rm s3://sagemaker-yolo-dev-up68ac/train-pipeline/ --recursive
```

If the job fails, the logs say why.

```sh
# the pipeline writes one processing job per execution
aws logs tail /aws/sagemaker/ProcessingJobs --follow
```
