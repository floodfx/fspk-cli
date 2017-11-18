# fspk

Install, Update, Configure, and Publish Function-as-a-Service Packages (a.k.a FaaSPack).

FaaSPacks are cloud functions that are meant to be installed directly into your cloud infrastructure.

# Installation

Simply run:

`pip install fspk`

# Getting Started

### Assumptions / Pre-reqs
* We assume you have an AWS account
* We assume you have AWS credentials setup
* We assume those credentials can:
  * Create / Manage IAM Roles
  * Create / Manage Lambda Functions
  * Create / Manage API Gateway

### Hello World
Install the `hello-world-faaspack` FaaSPack.

`fspk install hello-world-faaspack`

Assuming you have the AWS CLI installed
`aws lambda invoke --function-name hello-world-faaspack output.txt`

Now open output.txt and you should see:
`"Hello World"`

Try passing in a payload
`aws lambda invoke --function-name hello-world-faaspack --payload '{"name": "Jane"}' output.txt`

Now open output.txt and you should see:
`"Hello Jane"`

# Supported Clouds / FaaS Providers
We only support AWS currently but plan to support Azure, Google, and IBM along with other public clouds.  We also plan to support private and hybrid FaaS such as OpenFaaS.

# License
Apache 2.0
