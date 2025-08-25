const express = require('express');
const router = express.Router();

const items = [
  {
    id: 'laundry',
    title: "Laundry",
    desc: "Wash, dry, and fold any laundry in the basket.",
    completed: false
  },
  {
    id: 'bathroom',
    title: "Bathroom Deep Cleaning",
    desc: "Clean the bathroom from top to bottom, including the sink and shower. Clean Mercy's litterbox.",
    completed: false
  },
  {
    id: 'kitchen',
    title: "Kitchen Counter Cleaning",
    desc: "Clean the counter top, including under and behind any appliances. No 3Dness allowed.",
    completed: false
  },
  {
    id: 'dusting',
    title: "Dusting",
    desc: "Dust all surfaces, including the vinyl player, bookshelf, and any other surfaces.",
    completed: false
  },
  {
    id: 'vacuuming',
    title: "Vacuuming",
    desc: "Vacuum the floors, including the bathroom, kitchen, and any other rooms.",
    completed: false
  }
];

router.get('/', async (req, res) => {
  res.status(200).send(items);
});

router.post('/:id/toggle', express.json(), (req, res) => {
  const { id } = req.params;
  const { completed } = req.body;
  const item = items.find(i => i.id === id);
  if (item) {
    item.completed = completed;
    res.status(200).send({ message: `Toggled ${item.title}`, item });
  } else {
    res.status(404).send({ message: `Item ${item.title} not found` });
  }
});

router.post('/reset', (req, res) => {
  items.forEach(item => item.completed = false);
  res.status(200).send({ message: 'Reset all tasks', items });
});

module.exports = { router, items };
