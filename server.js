require('dotenv').config();

const firebase = require('firebase/app');
const firebaseAdmin = require('firebase-admin');
const firebaseAuth = require('firebase/auth');

const express = require('express');
const cors = require('cors');
const app = express();
app.use(cors());

const userRoutes = require('./users');
const habitRoutes = require('./habits');

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

// Listen to the App Engine-specified port, or 8080 otherwise
const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}...`);
});
