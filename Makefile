ARCH ?= arm64
TF    = terraform -chdir=terraform

.PHONY: help install test build init plan deploy demo destroy fmt clean

help:          ## Show this help
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install:       ## Install local test dependencies
	python3 -m pip install -r requirements-dev.txt

test:          ## Run unit tests (moto: no AWS account needed)
	python3 -m pytest -q tests

build:         ## Package Lambda code and the Pillow layer into build/
	./scripts/build.sh $(ARCH)

init:          ## terraform init
	$(TF) init

plan: build    ## Build, then terraform plan
	$(TF) plan -var="lambda_architecture=$(ARCH)"

deploy: build  ## Build, then terraform apply
	$(TF) apply -var="lambda_architecture=$(ARCH)"

demo:          ## Upload a sample image end to end: make demo IMG=path/to/photo.jpg
	./scripts/demo.sh $(IMG)

destroy:       ## Delete every resource (buckets are force-destroyed)
	$(TF) destroy -var="lambda_architecture=$(ARCH)"

fmt:           ## Format Terraform files
	$(TF) fmt -recursive

clean:         ## Remove build artefacts
	rm -rf build .pytest_cache
