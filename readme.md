## Work with SQS

I recommend working with SQS locally using LocalStack.

To create a queue:

```shell
awslocal sqs create-queue --queue-name UtilsQueue
```

To get queue url:

```shell
awslocal sqs get-queue-url --queue-name UtilsQueue
```

To read messages:

```shell
awslocal sqs receive-message --queue-url <queue-url> --max-number-of-messages 10 --message-attribute-names All --attribute-names All
```

To clear messages:

```shell
awslocal sqs purge-queue --queue-url <queue-url>
```
