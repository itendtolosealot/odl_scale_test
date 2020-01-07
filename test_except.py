from queue import Queue
import threading
import time
class QueueTest():
	_qh = Queue()
	_ql = threading.Lock()

	def __init__(self):
		self._t1 = threading.Thread(target=self.enqueue)
		self._t2 = threading.Thread(target=self.dequeue)
		self._t1.setDaemon(True)
		self._t2.setDaemon(True)
		self._t1.start()
		self._t2.start()

	def enqueue(self):
		for i in range(0,1000):
			self._ql.acquire()
			self._qh.put((i,i*i))
			self._ql.release()
			print("Put: " + str((i,i*i)))
			time.sleep(0.1)

	def dequeue(self):
		count = 0
		while count < 1000:
			if(self._qh.empty()):
				time.sleep(0.2)
				print("zero size")
			else:
				self._ql.acquire()
				result = self._qh.get()
				self._ql.release()
				print("Found: " + str(result))
				count = count+1


q = QueueTest()
