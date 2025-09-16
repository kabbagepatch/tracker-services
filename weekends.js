const express = require('express');
const router = express.Router();

const {Datastore} = require('@google-cloud/datastore');
const datastore = new Datastore();

const bodyParser = require('body-parser');
const jsonParser = bodyParser.json();

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

const getItems = async () => {
  const query = datastore.createQuery('WeekendTask').order('createdAt', { descending: false });
  const [tasks] = await datastore.runQuery(query);
  const tasksWithId = tasks.map(task => {
    task.id = task[datastore.KEY].name;
    return task;
  });

  return tasksWithId;
}

const updateItem = async (id, status) => {
  const itemKey = datastore.key(['WeekendTask', id]);
  const [item] = await datastore.get(itemKey);
  item.status = status;
  await datastore.save({ key: itemKey, data: item });

  return { ...item, id };
}

const resetItems = async () => {
  const tasks = await getItems();
  const resetTasks = tasks.map(task => {
    task.status = 'incomplete';
    return { key: task[datastore.KEY], data: task };
  });

  await datastore.upsert(resetTasks);

  return resetTasks.map(t => ({ ...t.data, id: t.key.name }));
}

router.get('/', async (req, res, next) => {
  try {
    const tasks = await getItems();
    res.status(200).send(tasks);
  } catch (err) {
    next(err);
  }
});

router.post('/', jsonParser, async (req, res, next) => {
  const {
    id,
    title,
    desc,
    status,
  } = req.body || {};

  if (!title) {
    return res.status(400).send('Task title is required');
  }

  try {
    const itemKey = datastore.key(['WeekendTask', id]);
    const curDate = new Date();
    const newItem = {
      key: itemKey,
      data: {
        title,
        desc,
        status: status || 'incomplete',
        createdAt: curDate,
      }
    }
    await datastore.save(newItem);
    res.status(201).json({ message: `Task ${itemKey.name} created`, item: { ...newItem.data, id: itemKey.id } });
  } catch (err) {
    next(err);
  }
});

router.post('/:id/toggle', jsonParser, async (req, res, next) => {
  const { id } = req.params;
  const { status } = req.body;

  try {
    const item = await updateItem(id, status);
    res.status(200).send({ message: `Toggled ${item.title}`, item });
  } catch (err) {
    next(err);
  }
});

router.post('/reset', async (req, res, next) => {
  try {
    res.status(200).send({ message: 'All tasks reset', items: await resetItems() });
  } catch (err) {
    next(err);
  }
});

router.post('/subscribe', express.json(), async (req, res, next) => {
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
