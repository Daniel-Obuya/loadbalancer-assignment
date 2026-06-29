# Build both images and start the stack
up:
	docker build -t server:latest ./server
	docker-compose up -d

# Stop everything and remove containers/images
down:
	docker-compose down
	docker rmi server:latest loadbalancer:latest 2>/dev/null || true

# View load balancer logs
logs:
	docker logs -f loadbalancer

# Quick test — check replicas
test:
	curl http://localhost:5000/rep