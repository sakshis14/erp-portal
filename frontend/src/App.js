import React from "react";

function App() {
  return (
    <div style={{ textAlign: "center", marginTop: "50px" }}>
      <h1>🚀 Shramic ERP Frontend</h1>
      <p>Frontend is running successfully using Docker 🎉</p>

      <button
        onClick={() => {
         window.location.href = "http://localhost:5000";
         }}
      
        style={{
          padding: "10px 20px",
          fontSize: "16px",
          backgroundColor: "blue",
          color: "white",
          border: "none",
          borderRadius: "5px",
          cursor: "pointer",
        }}
      >
        Go to ERP Backend
      </button>
    </div>
  );
}

export default App;