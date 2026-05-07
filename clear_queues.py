from azure.storage.queue import QueueClient

conn = "UseDevelopmentStorage=true"

queues = ["sensor-events", "sensor-events-poison"]

for q in queues:
    try:
        client = QueueClient.from_connection_string(conn, q)
        client.delete_queue()
        print(f"Deleted: {q}")
    except Exception as e:
        print(f"No existe o error en {q}: {e}")