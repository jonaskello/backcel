class BacktestMonitor:
    def __init__(self):
        self.messages = []

    def add(self, msg: str):
        self.messages.append(msg)

    def clear(self):
        self.messages = []

# Create one instance to be used everywhere
monitor = BacktestMonitor()