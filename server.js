require('dotenv').config();

const firebase = require('firebase/app');
const firebaseAdmin = require('firebase-admin');
const firebaseAuth = require('firebase/auth');

const express = require('express');
const app = express();

const cors = require('cors');
app.use(cors());

const { rateLimit } = require('express-rate-limit');
const limiter = rateLimit({
	windowMs: 15 * 60 * 1000, // 15 minutes
	limit: 100,
	standardHeaders: 'draft-8',
	legacyHeaders: false, // Disable the `X-RateLimit-*` headers.
	ipv6Subnet: 56,
})
app.use(limiter)

const helmet = require('helmet');
app.use(helmet());

const WebSocket = require('ws');
const http = require('http');
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const userRoutes = require('./users');
const habitRoutes = require('./habits');
const { router: weekendRoutes, items, sendNotifications, updateItem, getItems, resetItems } = require('./weekends');

const firebaseConfig = {
  apiKey: process.env.API_KEY,
  authDomain: 'habitsapi-426700.firebaseapp.com',
  projectId: 'habitsapi-426700',
  storageBucket: 'habitsapi-426700.appspot.com',
  messagingSenderId: '472591136365',
  appId: '1:472591136365:web:6129ffd560b9c66e7cf164',
  measurementId: 'G-TF2VLVQTLR'
};

firebase.initializeApp(firebaseConfig);
let serviceAccount;
if (process.env.ADMIN_ACCOUNT_KEY) {
  serviceAccount = JSON.parse(process.env.ADMIN_ACCOUNT_KEY);
} else {
  serviceAccount = require(process.env.ADMIN_ACCOUNT_JSON_PATH);
}
firebaseAdmin.initializeApp({
  credential: firebaseAdmin.credential.cert(serviceAccount)
});

const authenticate = async (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).send('Unauthorized');
  }

  try {
    let idToken;
    if (authHeader.includes('Basic ')) {
      const auth = firebaseAuth.getAuth();
      const decodedToken = atob(authHeader.split('Basic ')[1]).split(':');
      await firebaseAuth.signInWithEmailAndPassword(auth, decodedToken[0], decodedToken[1])
      req.user = auth.currentUser;
      next();
    } else if (authHeader.includes('Bearer ')) {
      const auth = firebaseAdmin.auth();
      idToken = authHeader.split('Bearer ')[1];
      req.user = await auth.verifyIdToken(idToken);
      next();
    } else {
      throw Error('No authorization found');
    }
  } catch (error) {
    console.log(error);
    return res.status(401).send('Unauthorized');
  }
};

app.options('*', cors());

app.get('/', (req, res) => {
  res.send('Hello from Habits App Engine!');
});

app.use('/users', userRoutes);
app.use('/habits', authenticate, habitRoutes);
app.use('/weekend-tasks', weekendRoutes);

wss.on('connection', async (ws) => {
  // send initial tasks
  ws.send(JSON.stringify({ type: 'init', items: await getItems() }));

  ws.on('message', async (message) => {
    const data = JSON.parse(message);
    console.log({ data });
    if (data.type === 'update' && data.item.status === 'complete') await sendNotifications(data.item);
    if (data.type === 'reset') await sendNotifications({ reset: true });
    wss.clients.forEach(async (client) => {
      if (client.readyState === WebSocket.OPEN) {
        if (data.type === 'update') {
          const item = await updateItem(data.item.id, data.item.status);
          // items.find(i => i.id === data.item.id).completed = data.item.completed;
          client.send(JSON.stringify({ type: 'update', item }));
        } else if (data.type === 'reset') {
          const items = await resetItems();
          // items.forEach(item => item.completed = false);
          client.send(JSON.stringify({ type: 'reset', items }));
        }
      }
    });
  });
});

// Listen to the App Engine-specified port, or 8080 otherwise
const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}...`);
});
