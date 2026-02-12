import * as firebaseAuth from 'firebase/auth';

import express from 'express';
const router = express.Router();

import { Datastore } from '@google-cloud/datastore';
import authenticate from './authenticate.js';
const datastore = new Datastore();

// Create
router.post('/', authenticate, async (req, res, next) => {
  const { uid, name, email } = req.user;
  try {
    const userExistsQuery = datastore
      .createQuery('User')
      .filter('email', '=', email.toLowerCase())
      .limit(1);
    const [existingUsers] = await datastore.runQuery(userExistsQuery);
    if (existingUsers.length > 0) {
      res.status(400).send('User already exists.')
      return;
    }

    const userKey = datastore.key(['User', uid]);
    const newUser = {
      key: userKey,
      data: {
        name,
        email: email.toLowerCase(),
        createdAt: new Date(),
      }
    };
    await datastore.save(newUser);
    res.status(201).json({ message: `User ${email} signed up` });
  } catch (err) {
    next(err);
  }
});

// Get all users
router.get('/', async (req, res, next) => {
  try {
    const query = datastore.createQuery('User');
    const [users] = await datastore.runQuery(query);
    const usersWithId = users.map(user => {
      user.id = user[datastore.KEY].name;
      return user;
    });
    res.status(200).send({ users: usersWithId });
  } catch (err) {
    next(err);
  }
});

// Get user by ID
router.get('/:id', authenticate, async (req, res, next) => {
  const { id } = req.params;
  try {
    const userKey = datastore.key(['User', id]);
    const [user] = await datastore.get(userKey);
    res.status(200).send({ user });
  } catch (err) {
    next(err);
  }
});

router.get('/admin/token', authenticate, async (req, res, next) => {
  try {
    const auth = firebaseAuth.getAuth();
    const decodedToken = atob(req.headers.authorization.split('Basic ')[1]).split(':');
    await firebaseAuth.signInWithEmailAndPassword(auth, decodedToken[0], decodedToken[1])
    res.status(200).send(auth.currentUser.accessToken);
  } catch (err) {
    next(err);
  }
});


export default router;
