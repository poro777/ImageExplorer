import { ref, shallowRef, onUnmounted } from "vue";

export function folderAdder() {
  const progress = ref(0);
  const total = ref(0);
  const status = ref("done");
  const socket = shallowRef(null);

  function start(path) {
    // Close any existing connection before starting a new one.
    if (socket.value) {
      socket.value.close();
    }

    const wsUrl = `ws://127.0.0.1:8000/ws/watcher/add?path=${encodeURIComponent(path)}`;
    const newSocket = new WebSocket(wsUrl);
    socket.value = newSocket;

    newSocket.onopen = () => {
      status.value = "processing";
    };

    newSocket.onmessage = (event) => {

      const data = JSON.parse(event.data);
      console.log("WebSocket message received:", data);
      
      if (data.status === "done") {
        status.value = "done";
        newSocket.close();
      } 
      else if (data.status === "processing") {
        status.value = "processing";
        progress.value = data.current;
        total.value = data.total; 
      }
      else if (data.error) {
        status.value = "error";
        newSocket.close();
      }
      
      
    };

    newSocket.onclose = () => {
      console.log("WebSocket closed");
      if (status.value === "processing") {
        status.value = "done";
      }
      socket.value = null;
    };

    newSocket.onerror = (error) => {
      console.error("WebSocket error:", error);
      status.value = "error";
    };
  }

  function stop() {
    if (socket.value) {
      socket.value.close();
    }
  }

  onUnmounted(() => {
    stop();
  });

  return { progress, status, total, start, stop };
}
