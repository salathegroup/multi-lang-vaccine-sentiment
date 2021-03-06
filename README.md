# Multi-language vaccine sentiment

This repository contains code & notebooks for different approaches to training multi-language vaccine sentiment models.

## Datasets

| Name          | Description           | Num examples  | Lang |
| ------------- | --------------------- | ------------- | ---- |
| `cb-en` | Stream (06/2017 - now) Keywords: "vaccine", "vaccination", "vaxxer", "vaxxed", "vaccinated", "vaccinating", "vacine", "overvaccinate", "undervaccinate", "unvaccinated" | 16.7M | en |
| `cb-pt` | Stream (09/2018 - now) Keywords: "vacina", "vacinação", "vacinado", "vacinar", "vacinal" | 7.3M | pt |
| `cb-de` | Stream (09/2019 - now) Keywords: "impf", "impfung", "geimpft" | 80k | de |
| `cb-fr` | Stream (09/2019 - now) Keywords: "vaccin", "vaccination", "vacciné" | 250k | fr |
| `cb-it` | Stream (09/2019 - now) Keywords: "vaccino", "vaccinazione", "vaccinato" | 154k | it |
| `cb-es` | Stream (09/2019 - now) Keywords: "vacuna", "vacunación", "vacunado", "vacunado" | 977k | es |

## Translated  datasets
| Name          | Description           | Num examples  | Source lang | Target lang |
| ------------- | --------------------- | ------------- | ---- |  ---- |
| `cb-en-fr` | Translated from `cb-en-sample`  | 10k | en | fr |
| `cb-en-es` | Translated from `cb-en-sample` | 10k | en | es |
| `cb-en-de` | Translated from `cb-en-sample` | 10k | en | de |


## Annotation datasets

| Name          | Description           | Num examples  | Lang |
| ------------- | --------------------- | ------------- | ---- |
| `cb-annot-en-original` | Classes: Positive, neutral, negative; 3-fold; unanimous; | 12.6k | en |
| `cb-annot-en` | Cleaned/deduplicated version of `cb-annot-en-original` | 10k | en |
| `cb-annot-en-sm` | Sampled from `cb-annot-en` | 5k | en |
| `cb-annot-pt` | Classes: Positive, neutral, negative; 3-fold; unanimous; is-relevant;  | 1.4k | pt |


## Translated annotation datasets

| Name          | Description           | Num examples  | Source lang | Target lang |
| ------------- | --------------------- | ------------- | ---- |  ---- |
| `cb-annot-en-fr` | Translated from `cb-annot-en`  | 10k | en | fr |
| `cb-annot-en-es` | Translated from `cb-annot-en` | 10k | en | es |
| `cb-annot-en-pt` | Translated from `cb-annot-en` | 10k | en | pt |
| `cb-annot-en-it` | Translated from `cb-annot-en` | 10k | en | it |
| `cb-annot-en-de` | Translated from `cb-annot-en` | 10k | en | de |
| `cb-annot-en-no` | Translated from `cb-annot-en` | 10k | en | no |
| `cb-annot-en-de-fr-es` | Translated from `cb-annot-en` | 50k | en | - |
| `cb-annot-en-fr-sm` | Translated from `cb-annot-en`  | 5k | en | fr |
| `cb-annot-en-es-sm` | Translated from `cb-annot-en` | 5k | en | es |
| `cb-annot-en-pt-sm` | Translated from `cb-annot-en` | 5k | en | pt |
| `cb-annot-en-it-sm` | Translated from `cb-annot-en` | 5k | en | it |
| `cb-annot-en-de-sm` | Translated from `cb-annot-en` | 5k | en | de |
| `cb-annot-en-no-sm` | Translated from `cb-annot-en` | 5k | en | no |
| `cb-annot-en-de-fr-es-sm` | Translated from `cb-annot-en` | 30k | en | - |


## Domain-specific pretraining datasets

| Name          | Description           | Num examples  | Lang |
| ------------- | --------------------- | ------------- | ---- |
| `cb-en` | Min 3 tokens; contains-keywords; no duplicate  | 4.8M | en |
| `cb-en-sample` | Min 3 tokens; contains-keywords; no duplicate; sampled from `cb-en`  | 100k | en |
| `lshtm` | Mix of news articles and tweets   | ? | en |



## Results

### English baseline results

| Experiment name          | Description | Pre-trained model | Domain pre-training | Classifier training | Accuracy | F1-macro |
| ------------- | ------------| ------------------| ------------------- | ------------------- |  ------- | -------- |
| - | - | `bert-large-uncased`  | - | `cb-annot-en` | 89.1% | ? |
| - | - | `bert-base-multilingual-uncased`  | - | `cb-annot-en` | 84% | ? |
| - | - | `bert-large-uncased` | `lshtm` | `cb-annot-en` | 92% | ? |

### Zero shot results

| Experiment name | Description | Pre-trained model | Domain pre-training | Classifier training | Evaluation dataset | Accuracy | F1-macro |
| ------------- | ------------| ------------------| ------------------- | ------------------- |  ------- | -------- | -------- |
| `zero-shot-en-de` | - | `bert-base-multilingual-uncased`  | - | `cb-annot-en` | `cb-annot-de` | - | - |


### Translated datasets results

| Experiment name | Description | Pre-trained model | Domain pre-training | Classifier training | Evaluation dataset | Accuracy | F1-macro |
| ------------- | ------------| ------------------| ------------------- | ------------------- |  ------- | -------- | -------- |
| `zeroshot-en-*` | - | `bert-base-multilingual-uncased`  | - | `cb-annot-en(/-sm)` | `cb-annot-*` | - | - |
| `translated-en-*` | - | `bert-base-multilingual-uncased`  | - | `cb-annot-en-*(/-sm)` | `cb-annot-*` | - | - |
| `multitranslated-en-*` | - | `bert-base-multilingual-uncased`  | - | `cb-annot-en-de-fr-es(/-sm)` | `cb-annot-*` | - | - |
| `balanced-en-*` | - | `bert-base-multilingual-uncased`  | - | `cb-annot-en-de-fr-es-(us/os)` | `cb-annot-*` | - | - |



### Training set distribution
| Class | Number | Percentage |
| ------------- | -----------:| -----------------:|
| positive	| 2447| 	40.78%| 
| neutral	| 3130	| 52.17%| 
| negative	| 423	| 7.05%| 
| 	| 6000	| 100%| 


### Cost of doing annotations
![Image of Cost Pyramid](https://raw.githubusercontent.com/salathegroup/multi-lang-vaccine-sentiment/master/static/pyramid.png)
