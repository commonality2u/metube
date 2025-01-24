# 1. Check Live Container Logs
docker ps -a --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"
docker logs -f metube  # Or use container ID

# 2. Verify Server Binding and Process Status
docker exec -it metube sh -c "ps aux | grep '[p]ython3 app/main.py'"
docker exec -it metube sh -c "netstat -tulpn | grep ':8081'"

# 3. Test Internal Container Networking
# Get container IP
$CONTAINER_IP = docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' metube

# Test internal connectivity
docker exec -it metube sh -c "wget -qO- http://localhost:8081/api/version"
curl.exe -v http://${CONTAINER_IP}:8081/api/version

# 4. Fix Permissions Issues
# Reset ownership of mounted volumes
docker exec -it metube sh -c "chown -R metube:metube /downloads/.metube"
docker exec -it metube sh -c "chmod -R 755 /downloads/.metube"

# Verify permissions
docker exec -it metube sh -c "ls -la /downloads/.metube"

# 5. Check Database Access
docker exec -it metube sh -c "sqlite3 /downloads/.metube/queue 'SELECT * FROM queue_items;'"
docker exec -it metube sh -c "sqlite3 /downloads/.metube/completed 'SELECT * FROM queue_items;'"
docker exec -it metube sh -c "sqlite3 /downloads/.metube/pending 'SELECT * FROM queue_items;'"

# 6. Verify File Structure
docker exec -it metube sh -c "tree /downloads/.metube"

# 7. Check for Python Errors
docker exec -it metube sh -c "cat /app/logs/error.log"
docker exec -it metube sh -c "cat /app/logs/debug.log"

# 8. Full Reset and Rebuild
docker-compose down -v
docker system prune -af --volumes
Remove-Item -Recurse -Force "D:\your\downloads\.metube"  # Adjust path as needed
docker-compose up -d --build

# 9. Monitor Resource Usage
docker stats metube

# 10. Debug Network Issues
docker network inspect bridge
docker exec -it metube sh -c "ping -c 4 8.8.8.8"
docker exec -it metube sh -c "curl -I https://www.youtube.com"

# 11. Check Container Environment
docker exec -it metube sh -c "env | sort"

# 12. Verify Python Dependencies
docker exec -it metube sh -c "pip list"

# 13. Test Database Integrity
docker exec -it metube sh -c '
for db in queue completed pending; do
    echo "Checking $db database:"
    sqlite3 "/downloads/.metube/$db" "PRAGMA integrity_check;"
done'

# 14. Check Log Rotation Status
docker exec -it metube sh -c "ls -lh /app/logs/"

# 15. Verify UI Assets
docker exec -it metube sh -c "ls -R /app/ui/" 