const express = require('express');
const router = express.Router();

const {Datastore} = require('@google-cloud/datastore');
const datastore = new Datastore();

const webpush = require('web-push');
const vapidKeys = {
  publicKey: process.env.VAPID_PUBLIC_KEY,
  privateKey: process.env.VAPID_PRIVATE_KEY
};
webpush.setVapidDetails(
  'mailto:' + process.env.VAPID_CONTACT_EMAIL,
  vapidKeys.publicKey,
  vapidKeys.privateKey
);

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

router.post('/subscribe', express.json(), async (req, res) => {
  //handle push subscription
  const subscription = req.body;
  console.log('Received subscription: ', subscription);

  try {
    const subscriptionKey = datastore.key('Subscription');
    await datastore.save({ key: subscriptionKey, data: subscription });
    res.status(201).send({ message: 'Subscription received' });
  } catch (err) {
    console.error('Error saving subscription: ', err);
    next(err);
  }
});

const sendNotifications = async (item) => {
  const query = datastore.createQuery('Subscription');
  const [subscriptions] = await datastore.runQuery(query);

  const payload = JSON.stringify(item);

  for (const subscription of subscriptions) {
    try {
      const res = await webpush.sendNotification(subscription, payload)
      console.log('Notification sent', subscription[datastore.KEY].id, res.statusCode);
    } catch (err) {
      console.error('Error sending notification, removing subscription', subscription[datastore.KEY].id);
      await datastore.delete(subscription[datastore.KEY]);
    }
  }
};

module.exports = { router, items, sendNotifications };
