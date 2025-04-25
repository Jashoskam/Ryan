const express = require("express");
const path = require("path");
const cors = require("cors");
const axios = require("axios");

const app = express();
const PORT = 5001;

// enable cors & json parsing
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

app.get("/", (req, res) => {
    res.sendFile(path.join(__dirname, "public", "index.html"));
});

// proxy requests to fastapi backend
app.post("/chat", async (req, res) => {
    try {
        const response = await axios.post("http://127.0.0.1:8000/chat", req.body);
        res.json(response.data);
    } catch (error) {
        console.error("Error connecting to AI:", error.message);
        res.status(500).json({ response: "AI server is not responding" });
    }
});

app.get("/logs", async (req, res) => {
    try {
        const response = await axios.get("http://127.0.0.1:8000/logs");
        res.json(response.data);
    } catch (error) {
        console.error("Error fetching logs:", error.message);
        res.status(500).json({ logs: ["Error fetching logs."] });
    }
});

app.listen(PORT, () => {
    console.log(`Server running at http://127.0.0.1:${PORT}`);
});
