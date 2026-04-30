---
layout: page
title: Code
subtitle: This is where most of my typing goes to.
description: Open-source projects by Shay Palachy-Affek, including Python packages, data science tools, AI workflow utilities, and Hebrew NLP community resources.
updated: April 2026
---

<!-- GENERATED: edit data/*.yml or automation sources instead of this file. -->

<section class="selected-projects">
  <h2>Selected Projects</h2>
  <ul>
    <li><strong><a href="#cachier">cachier</a></strong> - Persistent function caching with multiple local and shared backends.</li>
    <li><strong><a href="#pulearn">pulearn</a></strong> - Practical positive-unlabeled learning estimators and evaluation tools.</li>
    <li><strong><a href="#pdpipe">pdpipe</a></strong> - Composable pandas DataFrame transformation pipelines.</li>
  </ul>
</section>

## Data & ML Tools

<span id="pdpipe"></span>
**[pdpipe](https://pdpipe.readthedocs.io/en/latest/){:target="_blank"}** - A composable pipeline library for pandas DataFrames, with reusable stages for column operations, encoding, and data-preparation workflows. [[website](https://pdpipe.readthedocs.io/en/latest/){:target="_blank"}] [[GitHub](https://github.com/pdpipe/pdpipe){:target="_blank"}]

<span id="pulearn"></span>
**[pulearn](https://pulearn.github.io/pulearn/){:target="_blank"}** - Python estimators, metrics, guides, and examples for learning from positive and unlabeled data, including scikit-learn-compatible PU classifiers. [[website](https://pulearn.github.io/pulearn/){:target="_blank"}] [[documentation](https://pulearn.github.io/pulearn/doc/pulearn/){:target="_blank"}] [[GitHub](https://github.com/pulearn/pulearn){:target="_blank"}]

**[skift](https://github.com/shaypal5/skift){:target="_blank"}** - scikit-learn-compatible wrappers for Python fastText, including DataFrame-friendly classifiers and stacking-friendly text-model adapters.

**[awesome-twitter-data](https://github.com/shaypal5/awesome-twitter-data){:target="_blank"}** - A curated, CC0 awesome-list of Twitter/X datasets and related resources, with license and dataset-size notes where available.

**[stationarizer](https://github.com/shaypal5/stationarizer){:target="_blank"}** - A pandas-friendly time-series utility that applies ADF/KPSS unit-root checks, multiple-testing correction, differencing, and detrending to stationarize numeric series automatically.

## Python & AI Workflow Utilities

<span id="cachier"></span>
**[cachier](https://github.com/python-cachier/cachier){:target="_blank"}** - Persistent, stale-aware caching decorators for Python functions, with local files, memory, MongoDB, SQL, Redis, and S3 backends plus async support and cache analytics.

**[foldermix](https://github.com/foldermix/foldermix){:target="_blank"}** - A CLI that packs a folder into one LLM-friendly context file, with optional PDF, OCR, Office-document, and Markdown-conversion support.

**[pr-agent-context](https://github.com/shaypal5/pr-agent-context){:target="_blank"}** - A reusable GitHub Actions workflow that publishes managed PR handoff comments for coding agents, combining unresolved review threads, failing checks, log excerpts, and patch coverage.

**[birch](https://github.com/shaypal5/birch){:target="_blank"}** - Hierarchical configuration for Python packages and applications, reading namespaced settings from environment variables and JSON/YAML config files.

**[s3bp](https://github.com/shaypal5/s3bp){:target="_blank"}** - S3-backed persistence for Python objects, with local disk caching to avoid unnecessary downloads and special attention to pandas DataFrames.

**[morejson](https://github.com/shaypal5/morejson){:target="_blank"}** - A drop-in wrapper around Python's `json` API that adds encoding support for sets, complex numbers, dates, times, datetimes, timedeltas, and timezones.

## Community & Hebrew NLP

**[NLPH](https://github.com/NLPH/NLPH){:target="_blank"}** - The Open Natural Language Processing in Hebrew initiative, promoting open tools, resources, datasets, and collaboration for production-ready Hebrew NLP.

**[DataTalks](https://github.com/DataHackIL/DataTalks){:target="_blank"}** - A public archive of the Datahack DataTalks meetup series, collecting talks on machine learning, statistics, data engineering, and applied data science.

## Recent & Experimental

**[SynthBanshee](https://github.com/DataHackIL/SynthBanshee){:target="_blank"}** - A config-driven Datahack pipeline for generating synthetic Hebrew audio datasets, including dialogue generation, TTS rendering, acoustic augmentation, labeling, and QA.

**[hocrgen](https://github.com/HeOCR/hocrgen){:target="_blank"}** - Dataset operations tooling for HeOCR, covering source ingestion, rights filtering, normalization, review queues, deterministic splits, and benchmark/release assembly for Hebrew OCR data.

**[leadforge](https://github.com/leadforge-dev/leadforge){:target="_blank"}** - An opinionated framework for generating narrative-grounded synthetic CRM and go-to-market datasets from simulated commercial worlds.

**[splendor](https://github.com/splendor-dev/splendor){:target="_blank"}** - A local-first, git-native, schema-driven knowledge compiler for code and research repositories, keeping wiki pages, source manifests, runtime records, and planning objects in version control.

<!--### Other research-related stuff

* [Aalto homepage](http://users.ics.aalto.fi/japarkki/){:target="_blank"}-->
