#!/bin/bash
# Ollama tuned for HiveMind, and reachable from the containers.
#
# OLLAMA_HOST: the default binds loopback only, which a container cannot reach.
#   Note this also exposes Ollama to your local network - fine at home, worth a
#   thought on shared Wi-Fi.
# NUM_PARALLEL: a swarm fires every agent of a round at once.
# MAX_LOADED_MODELS: two, so the small voices and the larger judges both stay
#   resident instead of evicting each other every turn.

OLLAMA_HOST=${OLLAMA_HOST:-0.0.0.0:11434} \
OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL:-8} \
OLLAMA_MAX_LOADED_MODELS=${OLLAMA_MAX_LOADED_MODELS:-2} \
OLLAMA_MAX_QUEUE=${OLLAMA_MAX_QUEUE:-512} \
  ollama serve
