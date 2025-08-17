const firebaseAuth = require('firebase/auth');

const {Datastore} = require('@google-cloud/datastore');
const datastore = new Datastore();

const express = require('express');
const router = express.Router();

const server = require('./server');

const authenticate = async (req, res, next) => {
  const idToken = req.headers.authorization && req.headers.authorization.split('Bearer ')[1];
  if (!idToken) {
    return res.status(401).send('Unauthorized');
  }

  try {
    const decodedToken = await firebaseAdmin.auth().verifyIdToken(idToken);
    req.user = decodedToken;
    next();
  } catch (error) {
    console.log(error);
    return res.status(401).send('Unauthorized');
  }
};

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
router.get('/:id', async (req, res, next) => {
  const { id } = req.params;
  try {
    const userKey = datastore.key(['User', id]);
    const [user] = await datastore.get(userKey);
    res.status(200).send({ user });
  } catch (err) {
    next(err);
  }
});

// Delete user by ID
router.delete('/:id', async (req, res, next) => {  
  const auth = firebaseAuth.getAuth();
  await firebaseAuth.signInWithEmailAndPassword(auth, "kavishmunjal123@gmail.com", "#TestPass13")
  await auth.currentUser.delete()

  const { id } = req.params;
  try {
    const userKey = datastore.key(['User', datastore.int(id)]);
    await datastore.delete(userKey);
    res.status(204);
  } catch (err) {
    next(err);
  }
});

router.get('/admin/token', async (req, res, next) => {
  try {
    //habitsapi-426700-firebase-adminsdk-dol7n-5cd3b1e42e
    const auth = firebaseAuth.getAuth();
    const decodedToken = atob(req.headers.authorization.split('Basic ')[1]).split(':');
    await firebaseAuth.signInWithEmailAndPassword(auth, decodedToken[0], decodedToken[1])
    res.status(200).send(auth.currentUser.accessToken);
  } catch (err) {
    next(err);
  }
});


module.exports = router;
