import * as firebaseAuth from 'firebase/auth';
import firebaseAdmin from 'firebase-admin';

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
      // await firebaseAdmin.auth().setCustomUserClaims(req.user.uid, { admin: true })
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

export default authenticate;
