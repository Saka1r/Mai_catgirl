# download_model.py — запусти один раз
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
model.save('data/models/paraphrase-multilingual-MiniLM-L12-v2')
print("✅ Модель сохранена локально")
