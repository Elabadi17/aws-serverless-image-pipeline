# Runbook

Commands assume you are in the repo root and the stack is deployed. Set these once:

```bash
cd terraform
export TABLE=$(terraform output -raw images_table)
export SFN=$(terraform output -raw state_machine_arn)
export QUEUE=$(terraform output -raw uploads_queue_url)
export DLQ=$(terraform output -raw dlq_url)
cd ..
```

---

## Alarm: `…-dlq-not-empty`

Events could not be dispatched after 3 attempts. Nothing is lost — messages stay 14 days in the DLQ.

1. **Look at the messages** (without deleting them):

   ```bash
   aws sqs receive-message --queue-url "$DLQ" --max-number-of-messages 5 \
     --visibility-timeout 0 --query 'Messages[].Body' --output text
   ```

2. **Find the cause** in the dispatcher logs:

   ```bash
   aws logs tail /aws/lambda/img-pipeline-dev-dispatcher --since 1h --filter-pattern ERROR
   ```

   Typical causes: missing `states:StartExecution` permission, wrong `STATE_MACHINE_ARN`, Step Functions throttling.

3. **Fix**, deploy, then **redrive** the messages back to the main queue:

   ```bash
   aws sqs start-message-move-task \
     --source-arn $(aws sqs get-queue-attributes --queue-url "$DLQ" --attribute-names QueueArn --query Attributes.QueueArn --output text)
   ```

   Without `--destination-arn`, messages return to their original queue. Duplicates are harmless (execution name = imageId).

---

## Alarm: `…-executions-failed`

1. **List failed images** with the GSI (no scan):

   ```bash
   aws dynamodb query --table-name "$TABLE" --index-name status-createdAt-index \
     --key-condition-expression "#s = :s" \
     --expression-attribute-names '{"#s":"status"}' \
     --expression-attribute-values '{":s":{"S":"FAILED"}}' \
     --no-scan-index-forward --max-items 10
   ```

2. **Open the execution**: the record has `executionArn`.

   ```bash
   aws stepfunctions get-execution-history --execution-arn <executionArn> \
     --reverse-order --max-items 10
   ```

   Or open it in the Step Functions console for the graph view showing the failing state.

3. **Reprocess one image after the fix.** The execution name `imageId` is taken for 90 days, so start a new execution with a suffixed name:

   ```bash
   aws stepfunctions start-execution --state-machine-arn "$SFN" \
     --name "<imageId>-retry1" \
     --input '{"imageId":"<imageId>","bucket":"<source-bucket>","key":"uploads/<imageId>.jpg","sizeBytes":0}'
   ```

   Or use **Redrive** on the failed execution in the console (restarts from the failed state).

---

## Alarm: `…-queue-backlog`

Oldest message older than 5 minutes: the dispatcher isn't keeping up or is failing.

* Check dispatcher errors/throttles in the dashboard.
* If it's a legitimate burst, raise `dispatcher_max_concurrency` (Terraform variable) and apply.

---

## Alarm: `…-<function>-errors`

* `validate`: up to 10 errors per 5 min are tolerated, as rejected images raise `InvalidImageError`. Above that, check whether one client is sending bad files, or whether a Pillow upgrade broke decoding.
* Others: read the function's log group, `aws logs tail /aws/lambda/img-pipeline-dev-<function> --since 1h`.

---

## Useful one-liners

```bash
# Status of one image
curl -s "$(terraform -chdir=terraform output -raw api_endpoint)/images/<imageId>" | jq

# Queue depth
aws sqs get-queue-attributes --queue-url "$QUEUE" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# Invalidate a CloudFront path (rarely needed: keys are immutable)
aws cloudfront create-invalidation --distribution-id <id> --paths "/full/<imageId>.jpg"
```
