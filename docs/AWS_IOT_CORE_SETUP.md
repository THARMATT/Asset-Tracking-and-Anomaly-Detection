# AWS IoT Core Configuration Guide

This guide provides step-by-step instructions to configure AWS IoT Core for the **IoT-Based Smart Asset Tracking and Anomaly Detection System**.

---

## 1. Prerequisites
- An active AWS Account.
- Access to the **AWS IoT Core** console in your preferred region (e.g., `us-east-1` or `ap-south-1`).

---

## 2. Step 1: Create an IoT Policy

1. In the AWS Management Console, navigate to **IoT Core**.
2. In the left navigation pane, expand **Manage** $\rightarrow$ **Security** $\rightarrow$ click **Policies**.
3. Click **Create Policy**.
4. Configure policy details:
   - **Policy Name:** `AssetTrackerPolicy`
5. Click **JSON** tab and paste the following policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect"
      ],
      "Resource": [
        "arn:aws:iot:*:*:client/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "iot:Publish",
        "iot:Receive"
      ],
      "Resource": [
        "arn:aws:iot:*:*:topic/assets/tracking/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "iot:Subscribe"
      ],
      "Resource": [
        "arn:aws:iot:*:*:topicfilter/assets/tracking/*"
      ]
    }
  ]
}
```

6. Click **Create**.

---

## 3. Step 2: Create Things and X.509 Certificates

### A. Backend Subscriber Thing
1. In the left pane, expand **Manage** $\rightarrow$ **All devices** $\rightarrow$ click **Things**.
2. Click **Create things** $\rightarrow$ select **Create single thing** $\rightarrow$ click **Next**.
3. **Thing name:** `Flask_Asset_Backend`. Leave defaults and click **Next**.
4. Select **Auto-generate a new certificate (recommended)** $\rightarrow$ click **Next**.
5. In **Attach policies to certificate**, select `AssetTrackerPolicy` $\rightarrow$ click **Create thing**.
6. **Download Certificate Files Modal:**
   - Download **Device certificate** (save as `certificate.pem.crt`).
   - Download **Private key file** (save as `private.pem.key`).
   - Download **Root CA certificates** $\rightarrow$ Download **Amazon Root CA 1** (save as `AmazonRootCA1.pem`).
   - *Important:* Move these three files into `backend/certificates/`.
7. Click **Done**.

### B. Wokwi ESP32 Simulator Thing
1. Repeat the steps above to create a second thing named `ESP32_Asset_Tracker`.
2. Generate certificates and attach `AssetTrackerPolicy`.
3. Save the certificate contents; these will be placed in `wokwi/secrets.h`.

---

## 4. Step 3: Find Your IoT Data Endpoint

1. In AWS IoT Core, click **Settings** at the bottom of the left menu.
2. In the **Device data endpoint** section, copy the **Endpoint**:
   - Format: `xxxxxxxxxxxxxx-ats.iot.<region>.amazonaws.com`
3. Add this endpoint to `backend/.env`:
   ```env
   AWS_IOT_ENDPOINT=xxxxxxxxxxxxxx-ats.iot.<region>.amazonaws.com
   ```
