import express from 'express';
const router = express.Router();

import bodyParser from 'body-parser';
const jsonParser = bodyParser.json();

import { executeQuery, getItems, getItemsById, insertItem, removeItem, removeItems } from "./mysql.js"

export const initializeDatabase = async () => {
  await executeQuery(`
    CREATE TABLE IF NOT EXISTS Vinyls (
      id INT AUTO_INCREMENT PRIMARY KEY,
      album VARCHAR(255) NOT NULL,
      artist VARCHAR(255) NOT NULL,
      disc_hex VARCHAR(255) DEFAULT "#000",
      n_sides INT NOT NULL DEFAULT 2,
      image_url VARCHAR(255) NOT NULL,
      tags LONGTEXT,
      tracks LONGTEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);

  await executeQuery(`
    CREATE TABLE IF NOT EXISTS VinylPlays (
      id INT AUTO_INCREMENT PRIMARY KEY,
      vinyl INT NOT NULL,
      side INT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT FK_VinylSide FOREIGN KEY (vinyl)
      REFERENCES Vinyls(id)
    )
  `);
}

router.get('/album/search', async (req, res, next) => {
  const searchTerm = req.query.album;
  if (!searchTerm) {
    return res.status(400).send('Album search term required')
  }
  const url = `https://ws.audioscrobbler.com/2.0/?method=album.search&api_key=${process.env.LAST_FM_API_KEY}&album=${searchTerm}&format=json`;
  const result = await fetch(url);
  const data = await result.json();

  res.status(200).send(data.results.albummatches.album.filter(a => !!a.mbid).map(a => ({
    name: a.name,
    artist: a.artist,
    image: a.image[a.image.length - 1]['#text']
  })));
});

const getAlbum = async (artist, album) => {
  const url = `https://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key=${process.env.LAST_FM_API_KEY}&artist=${artist}&album=${album}&format=json`;
  const result = await fetch(url);
  const data = await result.json();

  return {
    name: data.album.name,
    artist: data.album.artist,
    tags: data.album.tags.tag.map(t => t.name),
    image: data.album.image[data.album.image.length - 1]['#text'],
    tracks: data.album.tracks.track.map(t => t.name),
  }
}

router.get('/album', async (req, res, next) => {
  const album = req.query.album;
  const artist = req.query.artist;
  if (!album || !artist) {
    return res.status(400).send('Album and Artist required')
  }

  const data = await getAlbum(artist, album);
  res.status(200).send(data);
});

router.get('/', async (req, res, next) => {
  try {
    const vinyls = await getItems('Vinyls')
    res.status(200).send(vinyls.map(v => ({
      id: v.id,
      album: v.album,
      artist: v.artist,
      tags: JSON.parse(v.tags),
      tracks: JSON.parse(v.tracks),
      imageURL: v.image_url,
      discColor: v.disc_hex,
      nSides: v.n_sides,
    })));
  } catch (err) {
    next(err);
  }
});

router.post('/', jsonParser, async (req, res, next) => {
  const {
    album,
    artist,
    nSides,
    discColor,
  } = req.body || {};

  if (!album) return res.status(400).send('Album name is required');
  if (!artist) return res.status(400).send('Artist name is required');

  const data = await getAlbum(artist, album);
  let columns = 'album,artist,tags,tracks,image_url';
  const values = [album, artist, JSON.stringify(data.tags), JSON.stringify(data.tracks), data.image];
  if (discColor) {
    columns += ',disc_hex'
    values.push(discColor);
  }
  if (nSides) {
    columns += ',n_sides'
    values.push(nSides);
  }

  try {
    const result = await insertItem('Vinyls', columns, values);
    res.status(201).send({ id: result.insertId, ...data });
  } catch (err) {
    next(err);
  }
});

router.get('/history', async (req, res, next) => {
  try {
    const query = `
      SELECT VinylPlays.id, Vinyls.album, Vinyls.artist, Vinyls.image_url, VinylPlays.side, VinylPlays.created_at
      FROM VinylPlays INNER JOIN Vinyls
      ON VinylPlays.vinyl = Vinyls.id
    `
    const result = await executeQuery(query);
    res.status(200).send(result.map(p => ({
      playId: p.id,
      album: p.album,
      artist: p.artist,
      imageURL: p.image_url,
      side: p.side,
      timestamp: p.created_at,
    })));
  } catch (err) {
    next(err);
  }
});

router.get('/:id', async (req, res, next) => {
  const { id } = req.params;
  try {
    const vinyl = await getItemsById('Vinyls', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }
    res.status(200).send({
      id: vinyl.id,
      album: vinyl.album,
      artist: vinyl.artist,
      discColor: vinyl.disc_hex,
      nSides: vinyl.n_sides,
      imageURL: vinyl.image_url,
      tags: JSON.parse(vinyl.tags),
      tracks: JSON.parse(vinyl.tracks),
    });
  } catch (err) {
    next(err);
  }
});

router.delete('/:id', async (req, res, next) => {
  const { id } = req.params;
  try {
    const vinyl = await getItemsById('Vinyls', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

    await removeItems('VinylPlays', `vinyl = ${id}`)
    await removeItem('Vinyls', id)
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

router.get('/:id/plays', jsonParser, async (req, res, next) => {
  const { id } = req.params;
  try {
    const vinyl = await getItemsById('Vinyls', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

    const result = await getItems('VinylPlays', 'vinyl = ?', [id]);
    res.status(200).send({
      album: vinyl.album,
      artist: vinyl.artist,
      plays: result.map(p => ({
        playId: p.id,
        side: p.side,
        timestamp: p.created_at,
      })),
    });
  } catch (err) {
    next(err);
  }
});

router.post('/:id/plays', jsonParser, async (req, res, next) => {
  const { id } = req.params;
  const {
    side,
  } = req.body || {};
  try {
    const vinyl = await getItemsById('Vinyls', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }
    if (side) {
      await insertItem('VinylPlays', 'vinyl,side', [id, side]);
    } else {
      const sideParams = [];
      for (let i = 0; i < vinyl.n_sides; i += 1) {
        sideParams.push([id, i + 1]);
      }
      await executeQuery('INSERT INTO VinylPlays (vinyl,side) VALUES ?', [sideParams]);
    }

    res.status(201).send();
  } catch (err) {
    next(err);
  }
});

router.delete('/:id/plays/:playId', jsonParser, async (req, res, next) => {
  const { playId } = req.params;
  try {
    await removeItem('VinylPlays', playId);
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

export default router;

// initializeDatabase();
