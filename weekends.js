const fs = require('fs');
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

const getItems = () => {
  const data = fs.readFileSync('weekend-tasks.json');
  return JSON.parse(data);
}

const updateItem = (id, status) => {
  const items = getItems();
  const item = items.find(i => i.id === id);
  if (item) {
    item.status = status;
    fs.writeFileSync('weekend-tasks.json', JSON.stringify(items, null, 2));
  }

  return item;
}

const resetItems = () => {
  const items = getItems();
  items.forEach(item => item.status = 'incomplete');
  fs.writeFileSync('weekend-tasks.json', JSON.stringify(items, null, 2));

  return items;
}

router.get('/', async (req, res) => {
  const items = getItems();
  res.status(200).send(items);
});

router.post('/:id/toggle', express.json(), (req, res) => {
  const { id } = req.params;
  const { status } = req.body;
  const updatedItem = updateItem(id, status);
  if (updatedItem) {
    res.status(200).send({ message: `Toggled ${updatedItem.title}`, item: updatedItem });
  } else {
    res.status(404).send({ message: `Item ${id} not found` });
  }
});

router.post('/reset', (req, res) => {
  const items = resetItems();
  res.status(200).send({ message: 'Reset all tasks', items });
});

router.post('/subscribe', express.json(), async (req, res) => {
  //handle push subscription
  const subscription = req.body;
  console.log('Received subscription: ', subscription);
  let id = 'kav';
  if (subscription.endpoint.includes('apple')) {
    id = 'bwi';
  }

  try {
    const subscriptionKey = datastore.key(['Subscription', id]);
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
    const id = subscription[datastore.KEY].id || subscription[datastore.KEY].name;
    try {
      await webpush.sendNotification(subscription, payload)
    } catch (err) {
      console.error('Error', err.statusCode, 'sending notification, removing subscription for', id);
      await datastore.delete(subscription[datastore.KEY]);
    }
  }
};

module.exports = { router, getItems, updateItem, resetItems, sendNotifications };
