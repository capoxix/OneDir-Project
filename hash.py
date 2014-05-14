import hashlib
def sha256_file(f):
	hash = hashlib.sha256()
	while True:
		data = f.read(4096)
		if not data:
			break
		hash.update(data)
	# f.close()has
	return hash.hexdigest()