FROM python:3.12-alpine
RUN addgroup -S -g 65532 sandbox && adduser -S -D -H -u 65532 -G sandbox sandbox
WORKDIR /workspace
USER 65532:65532
ENTRYPOINT []
CMD ["python","-c","print('GreyGuard isolated sandbox ready')"]
