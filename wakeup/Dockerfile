# 国内直连 Docker Hub 不通,走 AWS 公共镜像(和 xinchao3 一样的老办法)
FROM public.ecr.aws/docker/library/node:20-alpine
WORKDIR /app
COPY engine.js .
CMD ["node", "engine.js"]
