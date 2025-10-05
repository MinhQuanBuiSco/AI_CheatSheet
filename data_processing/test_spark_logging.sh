#!/bin/bash
# Test Spark Logging - Shows worker and job logs

echo "🚀 Testing Spark Logging"
echo "========================"
echo ""

# Step 1: Restart Spark with new config
echo "1️⃣  Restarting Spark with Log4j2 config..."
docker-compose restart spark-master spark-worker
sleep 5
echo "✅ Spark restarted"
echo ""

# Step 2: Check Spark is running
echo "2️⃣  Checking Spark status..."
docker-compose ps | grep spark
echo ""

# Step 3: Show current worker logs (startup)
echo "3️⃣  Worker startup logs:"
echo "---"
docker-compose logs --tail 10 spark-worker | head -20
echo ""

# Step 4: Submit a test Spark job
echo "4️⃣  Submitting test Spark job..."
echo ""
echo "Command:"
echo 'curl -X POST "http://localhost:8000/spark/process" \'
echo '  -H "Content-Type: application/json" \'
echo '  -d "{"input_path": "/app/data/claude_usage_logs.parquet", "output_path": "/app/output/spark_test/", "mode": "local", "spark_master": "spark://spark-master:7077"}"'
echo ""

curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/spark_test/",
    "mode": "local",
    "spark_master": "spark://spark-master:7077"
  }'
echo ""
echo ""

# Wait for job to process
echo "⏳ Waiting 5 seconds for job to start..."
sleep 5

# Step 5: Show job execution logs
echo ""
echo "5️⃣  Job execution logs:"
echo "---"
echo "📊 From API worker:"
docker-compose logs --tail 20 api | grep "Spark Job"
echo ""
echo "🔧 From Spark Master:"
docker-compose logs --tail 20 spark-master | grep -E "job-|application"
echo ""
echo "⚙️  From Spark Workers:"
docker-compose logs --tail 20 spark-worker | grep -E "executor|task|stage"
echo ""

# Step 6: Check persistent log files
echo "6️⃣  Persistent log files:"
echo "---"
ls -lh logs/spark-master/*.log 2>/dev/null || echo "❌ No master logs yet"
ls -lh logs/spark-workers/*.log 2>/dev/null || echo "❌ No worker logs yet"
echo ""

# Step 7: View Spark UI
echo "7️⃣  Spark UI available at:"
echo "   Master UI: http://localhost:8080"
echo "   Worker UI: http://localhost:8081"
echo ""

echo "✅ Test complete!"
echo ""
echo "💡 To view live logs:"
echo "   Master:  docker-compose logs -f spark-master"
echo "   Workers: docker-compose logs -f spark-worker"
echo "   API:     docker-compose logs -f api"
