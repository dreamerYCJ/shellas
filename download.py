from modelscope import snapshot_download

# 下载目录会保存在当前文件夹的 weights 目录下
model_dir = snapshot_download('Qwen/Qwen2.5-Coder-14B-Instruct-AWQ', cache_dir='./weights')
print(f"模型已下载到: {model_dir}")