# Web application

The public site for the project: `https://yolo.arguswatcher.net`.

Static frontend in `web/`, uploaded to `S3` by Terraform and served through
`CloudFront`. `/v1/*` is routed to the `Lambda` proxy in front of the
`SageMaker` serverless endpoint, so the browser sees a single origin and CORS
never applies.

Built on `Bootstrap 5.3.8` in dark mode (`data-bs-theme="dark"`), matching the
house style of [trip-ml.arguswatcher.net](https://trip-ml.arguswatcher.net/).

---

## Outline

### navbar

Fixed-top, translucent with blur. Brand on the left, anchor links on the right,
collapsing to a hamburger below `lg`.

- brand: `Car Plate Detection`
- links: Challenge · Detect · Machine Learning · CPU vs GPU · Inference

---

### hero

Full-height, centred, with a dark scrim over the background so the headline
stays readable.

- title: `License Plate Recognition MLOps`
- subtitle: `End-to-end MLOps workflow` (uppercase, letter-spaced, brand colour)
- content: An `Amazon SageMaker` project that trains and deploys a `YOLO`
  object-detection model through a full MLOps workflow — from labelled images
  to a serverless inference endpoint behind a public web app.
- left button: `Try the model` → `#detect`
- right button: `GitHub Repository` → repo URL

---

### Business Challenge

Narrative section. Lead paragraph, a pull-quote `statement` with a brand-coloured
left rule, then a closing paragraph.

- lead: Computer vision models like `YOLO` are popular for object detection in
  manufacturing.
- statement: *Integrating these computer vision models reliably into business
  applications* remains a significant challenge.
- close: This project demonstrates an end-to-end MLOps workflow by training,
  deploying, and serving a `YOLO` model that detects vehicle license plates.
- note: OCR is out of scope — the model detects plate regions, it does not read
  them.

---

### try model

The live demo, on an alternate-surface section so it reads as the interactive
part of the page.

- title: `License Plate Recognition`
- subtitle: The deployed model, served from a `SageMaker` serverless endpoint
  through a `Lambda` proxy. Pick an image and run detection.
- card contents:
  - model status badge (readiness probe: `GET /v1/models/{model}`)
  - file picker (`jpeg`/`png`)
  - confidence slider, `0.05`–`0.95`, default `0.25`
  - `Detect` button, disabled until an image is chosen
  - canvas: the image with detection boxes drawn over it
  - results table: `#`, class, confidence, box `(x1, y1, x2, y2)`
  - message line: filename, dimensions, detection count, elapsed ms, errors
- request: `POST /v1/models/{model}:predict` with
  `{instances:[{image:{b64}, conf}]}`
- limit: 6 MB base64 — the serverless endpoint's request cap.

---

### Machine Learning

Bullet points over the MLOps lifecycle, then a carousel of the supporting
screenshots.

- bullet points (the six lifecycle stages):
  1. **Data collection** — collect images of license plates.
  2. **Feature engineering** — label images.
  3. **Model training and experiment tracking** — run training code with a
     `SageMaker pipeline` and log metrics to `MLflow`.
  4. **Evaluate model** — register the model only when `mAP50-95` clears the
     `0.70` gate.
  5. **Package and deploy** — serve the model from a `SageMaker` serverless
     endpoint.
  6. **Integrate** the inference endpoint with the web application.

- carousel slides:
  - pipeline — `SageMaker` pipeline automating training (`sagemaker_pipeline02.png`)
  - jupyter notebook — model development (`notebook_train_cpu01.png`)
  - mlflow metrics — training metrics tracked in `MLflow` (`mlflow_metrics01.png`)
  - hyperparameter sweep — sweep for best performance (`mlflow_traintime01.png`)

---

### cpu vs gpu

The same model, dataset, and hyperparameters trained on each instance type.

- title: `CPU vs GPU`
- table:

  | Instance | Specification | GPU | Rate per hour($) | Total min | Total cost($) |
  | --- | --- | --- | --- | --- | --- |
  | `ml.m5.xlarge(cpu)` | 4vCPU, 16 GiB | N/A | 0.257 | 27.8 | 0.379 |
  | `ml.g4dn.xlarge(gpu)` | 4vCPU, 16 GiB | Yes | 0.818 | 2.2 | 0.029 |

  The GPU instance costs ~3x more per hour but finishes ~13x faster, so the run
  is roughly **13x cheaper** overall.

- images:
  - train time — cpu `27.8m` vs gpu `2.2m` (`cpu_vs_gpu01.png`)
  - cpu% vs gpu% — cpu run (blue) ~75% cpu; gpu run (red) ~75% cpu, ~15% gpu
    (`cpu_vs_gpu02.png`)

  Low GPU utilisation indicates the run is input-bound rather than
  compute-bound — headroom for a larger batch or faster data loading.

---

### inference

- bullet points:
  1. **Promote the model** — approve a version in the `sagemaker-yolo` model
     package group.
  2. **Serve** the approved model from a `SageMaker` serverless endpoint, so
     idle time costs nothing.
  3. **Integrate** the endpoint with the web application through the `Lambda`
     proxy behind `CloudFront`.

- architecture diagram: `architecture.gif`

---

### footer

- left: `Arguswatcher` @2026
- right: links to the documentation and the GitHub repository

---

## Files

```
web/
├── index.html            markup
├── css/style.css         site styles layered on Bootstrap
├── js/main.js            demo client: readiness, predict, canvas, table
├── img/                  screenshots used by the page
└── nginx.conf.template   local/compose serving only, not used on CloudFront
```

`Bootstrap` and `Popper` load from the jsDelivr CDN with SRI hashes.

---

## Deployment

`infra/deploy_s3.tf` uploads `web/` to `s3://<bucket>/web/` and sets
`Content-Type` from the file extension. The fileset and the content-type map
both have to list an extension for a file to be served correctly — `html`,
`css`, `js`, `png`, `jpg`, `gif`, `svg`, and `ico` are covered.

`infra/deploy_cloudfront.tf` puts `CloudFront` in front of it:

- default behaviour → `s3-web` origin, caching optimized
- `/v1/*` → `Lambda` function URL origin, caching disabled

After changing anything under `web/`, re-apply the deploy stack and invalidate
the distribution so `CloudFront` picks up the new objects.
