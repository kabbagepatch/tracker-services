import express from 'express';
const router = express.Router();

import bodyParser from 'body-parser';
const jsonParser = bodyParser.json();

import * as datastore from './datastore.js';
import { getReleaseDiscogs, getAlbumDiscogs, getPixelsAsync, extractColorsAsync } from './music.js';

const validateOwnership = async (req, res, next) => {
  const { id } = req.params;
  const { uid } = req.user;

  try {
    const vinyl = await datastore.get('Vinyl', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }
    if (vinyl.userId !== uid) {
      return res.status(403).send('Forbidden: You do not have access to this vinyl');
    }

    req.vinyl = vinyl;
    next();
  } catch (err) {
    next(err);
  }
}

router.get('/', async (req, res, next) => {
  const { uid } = req.user;

  try {
    const vinyls = await datastore.query('Vinyl', { property: 'userId', operator: '=', value: uid });
    res.status(200).send(vinyls);
  } catch (err) {
    next(err);
  }
});

router.post('/', jsonParser, async (req, res, next) => {
  const { uid } = req.user;
  const {
    album,
    artist,
    discogsId,
    nSides,
    discColor,
  } = req.body || {};

  if (!discogsId && (!album || !artist)) {
    return res.status(400).send('Either discogs ID or album and artist names required');
  }

  const discogsReleaseData = await getReleaseDiscogs(discogsId);
  if (discogsId && !discogsReleaseData) {
    return res.status(400).send('Invalid Discogs ID');
  }
  const discogsMastersData = await getAlbumDiscogs(discogsReleaseData.masterId);
  const albumColors = await extractColorsAsync(discogsMastersData.imageUrl || discogsReleaseData.imageUrl);

  const data = {
    userId: uid,
    discogsReleaseId: discogsReleaseData.id,
    discogsMastersId: discogsReleaseData.masterId,
    album: album || discogsReleaseData.album,
    artist: artist || discogsReleaseData.artist,
    nSides: nSides || discogsReleaseData.nSides,
    discColor: discColor || discogsReleaseData.discColor,
    genres: discogsMastersData.genres.concat(discogsMastersData.styles),
    tracks: discogsReleaseData.tracks,
    imageUrl: discogsMastersData.imageUrl || discogsReleaseData.imageUrl,
    albumImageUrl: discogsMastersData.imageUrl,
    vinylImageUrl: discogsReleaseData.imageUrl,
    published: discogsMastersData.published,
    favorite: false,
    albumColors,
  };

  try {
    const id = await datastore.save('Vinyl', data);
    res.status(201).send({ id, ...data });
  } catch (err) {
    next(err);
  }
});

router.get('/history', async (req, res, next) => {
  const { uid } = req.user;

  try {
    const history = await datastore.query('VinylPlay', { property: 'userId', operator: '=', value: uid });
    
    const vinylIds = history.map(p => p.vinylId);
    const vinyls = await datastore.getMultiple('Vinyl', vinylIds);
    const vinylMap = {}
    vinyls.forEach(v => {
      vinylMap[v.id] = v;
    });
    const result = history.filter(play => !!vinylMap[play.vinylId]).map((play) => {
      const fullHistory = {
        ...play,
        playId: play.id,
        album: vinylMap[play.vinylId].album,
        artist: vinylMap[play.vinylId].artist,
        imageUrl: vinylMap[play.vinylId].imageUrl,
        nSides: vinylMap[play.vinylId].nSides,
        albumColors: vinylMap[play.vinylId].albumColors,
      }
      delete fullHistory.id;
      return fullHistory;
    })
    result.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    res.status(200).send(result);
  } catch (err) {
    next(err);
  }
});

router.get('/:id', validateOwnership, async (req, res, next) => {
  try {
    res.status(200).send(req.vinyl);
  } catch (err) {
    next(err);
  }
});

router.put('/:id', jsonParser, validateOwnership, async (req, res, next) => {
  const { id } = req.params;
  const {
    album,
    artist,
    published,
    nSides,
    discColor,
  } = req.body || {};

  try {
    const vinyl = req.vinyl;
    const updatedVinyl = {
      ...vinyl,
      album: album || vinyl.album,
      artist: artist || vinyl.artist,
      published: published || vinyl.published,
      nSides: nSides || vinyl.nSides,
      discColor: discColor || vinyl.discColor,
      updatedAt: new Date(),
    };
    await datastore.update('Vinyl', id, updatedVinyl);
    res.status(200).send(updatedVinyl);
  } catch (err) {
    next(err);
  }
});

router.put('/:id/favorite', jsonParser, validateOwnership, async (req, res, next) => {
  const { id } = req.params;
  const { favorite } = req.body || {};

  try {
    const updatedVinyl = { ...req.vinyl, favorite };
    await datastore.update('Vinyl', id, updatedVinyl);
    res.status(200).send(updatedVinyl);
  } catch (err) {
    next(err);
  }
});

router.delete('/:id', validateOwnership, async (req, res, next) => {
  const { id } = req.params;

  try {
    const vinyl = req.vinyl;
    const result = await datastore.query('VinylPlay', {
      property: 'vinylId', operator: '=', value: id,
    });
    if (result.length > 0) {
      return res.status(400).send(`Cannot delete vinyl ${vinyl.album} from catalog. Vinyl has plays recorded`);
    }

    await datastore.del('Vinyl', id);
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

router.get('/:id/plays', validateOwnership, async (req, res, next) => {
  const { id } = req.params;

  try {
    const vinyl = req.vinyl;
    const result = await datastore.query('VinylPlay', {
      property: 'vinylId', operator: '=', value: id,
    });

    res.status(200).send({
      album: vinyl.album,
      artist: vinyl.artist,
      plays: result.map(p => ({
        playId: p.id,
        sides: p.sides,
        timestamp: p.timestamp,
      })),
    });
  } catch (err) {
    next(err);
  }
});

router.post('/:id/plays', jsonParser, validateOwnership, async (req, res, next) => {
  const { id } = req.params;
  const { uid } = req.user;
  const { sides, date } = req.body || {};

  let timestamp = new Date();
  if (date) {
    try {
      timestamp = new Date(date);
    } catch (e) {
      return res.status(400).send('Invalid Date String passed in');
    }
  }

  try {
    const vinyl = req.vinyl;
    const data = {
      userId: uid,
      vinylId: id,
      sides,
      timestamp,
    }
    const playId = await datastore.save('VinylPlay', data);
    res.status(201).send({
      playId,
      ...data,
      album: vinyl.album,
      artist: vinyl.artist,
      imageUrl: vinyl.imageUrl,
      nSides: vinyl.nSides,
    });
  } catch (err) {
    next(err);
  }
});

router.delete('/:id/plays/:playId', validateOwnership, async (req, res, next) => {
  const { id, playId } = req.params;
  const { uid } = req.user;

  try {
    const play = await datastore.get('VinylPlay', playId);
    if (play.userId !== uid) {
      return res.status(403).send('Forbidden: You do not have access to this vinyl');
    }
    if (play.vinylId !== id) {
      return res.status(400).send('Vinyl Id does not match Vinyl Play');
    }

    await datastore.del('VinylPlay', playId);
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

export default router;
