import express from 'express';
const router = express.Router();

import bodyParser from 'body-parser';
const jsonParser = bodyParser.json();

import * as datastore from './datastore.js';

/* External APIs */

router.get('/album/lastfm/search', async (req, res, next) => {
  const searchTerm = req.query.album;
  if (!searchTerm) {
    return res.status(400).send('Album search term required')
  }
  const url = `https://ws.audioscrobbler.com/2.0/?method=album.search&api_key=${process.env.LAST_FM_API_KEY}&album=${searchTerm}&format=json`;
  const result = await fetch(url);
  const data = await result.json();

  res.status(200).send(data.results.albummatches.album.filter(a => !!a.mbid).map(a => ({
    album: a.name,
    artist: a.artist,
    imageUrl: a.image[a.image.length - 1]['#text']
  })));
});

const getAlbumLastFM = async (artist, album) => {
  try {
    const url = `https://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key=${process.env.LAST_FM_API_KEY}&artist=${artist}&album=${album}&format=json`;
    const result = await fetch(url);
    const data = await result.json();

    return {
      album: data.album.name,
      artist: data.album.artist,
      tags: data.album.tags ? data.album.tags.tag.map(t => t.name) : [],
      imageUrl: data.album.image[data.album.image.length - 1]['#text'],
      thumbnailUrl: data.album.image[1]['#text'],
      published: data.album.wiki ? new Date(data.album.wiki.published).getFullYear() : undefined,
      tracks: data.album.tracks && data.album.tracks.track ? data.album.tracks.track.map(t => t.name) : [],
    }
  } catch (e) {
    console.log(e.message);
  }
}

router.get('/album/lastfm', async (req, res, next) => {
  const album = req.query.album;
  const artist = req.query.artist;
  if (!album || !artist) {
    return res.status(400).send('Album and Artist required')
  }

  const data = await getAlbumLastFM(artist, album);
  res.status(200).send(data);
});

router.get('/album/discogs/search', async (req, res, next) => {
  const searchTerm = req.query.album;
  if (!searchTerm) {
    return res.status(400).send('Album search term required')
  }
  const url = `https://api.discogs.com/database/search?q=${searchTerm}&type=release&format=Vinyl`;
  const result = await fetch(url, {
    headers: {
      "Authorization": `Discogs key=${process.env.DISCOGS_KEY}, secret=${process.env.DISCOGS_SECRET}`
    }
  });
  const data = await result.json();

  res.status(200).send(data.results.map(v => ({
    discogsId: v.id,
    title: v.title,
    published: v.year,
    genres: v.genre,
    thumbnailUrl: v.thumb,
    imageUrl: v.cover_image,
    discColor: v.formats?.length && v.formats[0].text ? v.formats[0].text : 'Black',
  })));
});

const getAlbumDiscogs = async (discogsId) => {
  if (!discogsId) return;

  try {
    const url = `https://api.discogs.com/releases/${discogsId}`;
    const result = await fetch(url);
    const data = await result.json();

    return {
      album: data.title,
      artist: data.artists[0].name,
      genres: data.genres,
      imageUrl: data.images[0].uri,
      published: data.year,
      discColor: data.formats?.length && data.formats[0].text ? data.formats[0].text : 'Black',
      tracks: data.tracklist.map(t => ({ position: t.position, title: t.title })),
    }
  } catch (e) {
    console.log(e.message);
  }
}

router.get('/album/discogs/:id', async (req, res) => {
  const { id } = req.params;
  const data = await getAlbumDiscogs(id);
  res.status(200).send(data);
});

/* Vinyl Tracker APIs */

router.get('/', async (req, res, next) => {
  try {
    const vinyls = await datastore.query('Vinyl');
    res.status(200).send(vinyls);
  } catch (err) {
    next(err);
  }
});

router.post('/', jsonParser, async (req, res, next) => {
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

  const discogsData = await getAlbumDiscogs(discogsId);
  if (discogsId && !discogsData) {
    return res.status(400).send('Invalid Discogs ID');
  }

  const data = {
    album: album || discogsData.album,
    artist: artist || discogsData.artist,
    nSides,
    discColor: discColor || discogsData.discColor,
    genres: discogsData.genres,
    tracks: discogsData.tracks,
    imageUrl: discogsData.imageUrl,
    published: discogsData.published,
  };

  try {
    const id = await datastore.save('Vinyl', data);
    res.status(201).send({ id, ...data });
  } catch (err) {
    next(err);
  }
});

router.get('/history', async (req, res, next) => {
  try {
    const history = await datastore.query('VinylPlay');

    const vinylIds = history.map(p => p.vinylId);
    const vinyls = await datastore.get_multiple('Vinyl', vinylIds);
    history.forEach((v, i) => {
      history[i] = {
        ...history[i],
        playId: history[i].id,
        album: vinyls[i].album,
        artist: vinyls[i].artist,
        imageUrl: vinyls[i].imageUrl,
      }
      delete history[i].id
    })

    res.status(200).send(history);
  } catch (err) {
    next(err);
  }
});

router.get('/:id', async (req, res, next) => {
  const { id } = req.params;
  try {
    const vinyl = await datastore.get('Vinyl', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

    res.status(200).send(vinyl);
  } catch (err) {
    next(err);
  }
});

router.put('/:id', jsonParser, async (req, res, next) => {
  const { id } = req.params;
  const {
    published,
    nSides,
    discColor,
  } = req.body || {};

  try {
    const vinyl = await datastore.get('Vinyl', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

    const updatedVinyl = {
      ...vinyl,
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

router.delete('/:id', async (req, res, next) => {
  const { id } = req.params;
  try {
    const vinyl = await datastore.get('Vinyl', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

    await datastore.del('Vinyl', id);
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

router.get('/:id/plays', jsonParser, async (req, res, next) => {
  const { id } = req.params;
  try {
    const vinyl = await datastore.get('Vinyl', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

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

router.post('/:id/plays', jsonParser, async (req, res, next) => {
  const { id } = req.params;
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
    const vinyl = await datastore.get('Vinyl', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

    const data = {
      vinylId: id,
      sides,
      timestamp,
    }
    const playId = await datastore.save('VinylPlay', data);
    res.status(201).send({ playId, ...data });
  } catch (err) {
    next(err);
  }
});

router.delete('/:id/plays/:playId', jsonParser, async (req, res, next) => {
  const { playId } = req.params;
  try {
    await datastore.del('VinylPlay', playId);
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

export default router;
