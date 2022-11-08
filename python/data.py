import datasets as hf

def load_dataset():
    hf.load_dataset("bigcode/the-stack", data_dir="data/c", streaming=True, split="train")