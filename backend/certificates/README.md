# AWS IoT Core Certificates Directory

This directory stores the X.509 client certificates and keys required for mutual TLS (mTLS) authentication between the Python backend and AWS IoT Core.

## Required Files

1. `AmazonRootCA1.pem` - AWS Root Certificate Authority 1
2. `certificate.pem.crt` - Device/Client Certificate issued by AWS IoT Core
3. `private.pem.key` - Client Private Key generated during AWS IoT certificate creation

## Security Warning

- **NEVER** commit `.pem`, `.crt`, or `.key` files to GitHub or any public version control.
- These files are explicitly ignored by `.gitignore`.
- Provide the paths to these files in `backend/.env` using the following variables:
  ```env
  AWS_ROOT_CA_PATH="backend/certificates/AmazonRootCA1.pem"
  AWS_CERT_PATH="backend/certificates/certificate.pem.crt"
  AWS_KEY_PATH="backend/certificates/private.pem.key"
  ```
