#!/bin/bash
# Test GPT-OSS via Ollama Cloud - Cold vs Warm Start

echo "========================================="
echo "GPT-OSS 20B Cloud - Cold Start Test"
echo "========================================="
time ollama run gpt-oss:20b-cloud "Say hello in one word."

echo ""
echo "========================================="
echo "GPT-OSS 20B Cloud - Warm Start Test (immediate retry)"
echo "========================================="
time ollama run gpt-oss:20b-cloud "Say goodbye in one word."

echo ""
echo "========================================="
echo "GPT-OSS 120B Cloud - Cold Start Test"
echo "========================================="
time ollama run gpt-oss:120b-cloud "What is 2+2? Answer with just the number."

echo ""
echo "========================================="
echo "GPT-OSS 120B Cloud - Warm Start Test (immediate retry)"
echo "========================================="
time ollama run gpt-oss:120b-cloud "What is 3+3? Answer with just the number."

echo ""
echo "========================================="
echo "Comparison with DeepSeek V3.2 Cloud"
echo "========================================="
time ollama run deepseek-v3.2:cloud "What is 5+5? Answer with just the number."

echo ""
echo "========================================="
echo "Tests completed!"
echo "========================================="
