from modelscope import snapshot_download

model_dir = snapshot_download('Qwen/Qwen2.5-Coder-14B-Instruct-AWQ', cache_dir='./weights')
print(f"模型已下载到: {model_dir}")
