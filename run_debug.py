import traceback
from core.worker import Worker
worker = Worker('test')
try:
    worker._generate_features_batch([(36.96, -122.05)])
except Exception as e:
    traceback.print_exc()
