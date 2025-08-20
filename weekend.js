const express = require("express");
const router = express.Router();

const bodyParser = require('body-parser');
const jsonParser = bodyParser.json();

const tasks = [
  {
    title: "Laundry",
    desc: "Wash, dry, and fold any laundry in the basket.",
    completed: false
  },
  {
    title: "Bathroom Deep Cleaning",
    desc: "Clean the bathroom from top to bottom, including the sink and shower. Clean Mercy's litterbox.",
    completed: false
  },
  {
    title: "Kitchen Counter Cleaning",
    desc: "Clean the counter top, including under and behind any appliances. No 3Dness allowed.",
    completed: false
  },
  {
    title: "Dusting",
    desc: "Dust all surfaces, including the vinyl player, bookshelf, and any other surfaces.",
    completed: false
  },
  {
    title: "Vacuuming",
    desc: "Vacuum the floors, including the bathroom, kitchen, and any other rooms.",
    completed: false
  }
];

let clients = [];

router.get("/events", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");

  res.write(`data: ${JSON.stringify({ type: "init", tasks })}\n\n`);
  if (res.flush) res.flush();

  clients.push(res);

  req.on("close", () => {
    clients = clients.filter((c) => c !== res);
  });
});

router.post("/toggle", jsonParser, (req, res) => {
  console.log("Toggle request received:", req.body);
  const { title, completed } = req.body;
  const task = tasks.find((t) => t.title === title);
  if (task) {
    task.completed = completed;
    const payload = `data: ${JSON.stringify({ type: "update", tasks })}\n\n`;
    clients.forEach((c) => {
      c.write(payload)
      if (c.flush) c.flush();
    });
  }

  res.json({ success: true });
});

router.get("/", (req, res) => {
  res.json(tasks);
});

setInterval(() => {
  clients.forEach((res) => {
    res.write(":\n\n"); // SSE comment = keepalive
    if (res.flush) res.flush();
  });
}, 30000);

module.exports = router;
