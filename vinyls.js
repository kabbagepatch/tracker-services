import express from 'express';
const router = express.Router();

import bodyParser from 'body-parser';
const jsonParser = bodyParser.json();

import { executeQuery, getItems, getItemsById, insertItem, removeItem, removeItems } from "./mysql.js"

export const initializeDatabase = async () => {
  await executeQuery('DROP TABLE VinylPlays');
  await executeQuery('DROP TABLE Vinyls');
  await executeQuery(`
    CREATE TABLE IF NOT EXISTS Vinyls (
      id INT AUTO_INCREMENT PRIMARY KEY,
      album VARCHAR(255) NOT NULL,
      artist VARCHAR(255) NOT NULL,
      disc_color VARCHAR(255) DEFAULT "#000",
      n_sides INT DEFAULT 2,
      image_url VARCHAR(255),
      thumbnail_url VARCHAR(255),
      published VARCHAR(4),
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
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT FK_VinylSide FOREIGN KEY (vinyl)
      REFERENCES Vinyls(id)
    )
  `);
}

const vinylMap = (v) => {
  return {
    id: v.id,
    album: v.album,
    artist: v.artist,
    tags: JSON.parse(v.tags),
    tracks: JSON.parse(v.tracks),
    imageUrl: v.image_url,
    thumbnailUrl: v.thumbnail_url,
    published: v.published,
    discColor: v.disc_color,
    nSides: v.n_sides,
  }
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
    album: a.name,
    artist: a.artist,
    imageUrl: a.image[a.image.length - 1]['#text']
  })));
});

const getAlbum = async (artist, album) => {
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
    res.status(200).send(vinyls.map(vinylMap));
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

  const data = await getAlbum(artist, album) || {};
  let columns = 'album,artist,image_url,thumbnail_url';
  const values = [album, artist, data.imageUrl, data.thumbnailUrl];
  if (data.tags?.length > 0) {
    columns += ',tags'
    values.push(JSON.stringify(data.tags));
  }
  if (data.tracks?.length > 0) {
    columns += ',tracks'
    values.push(JSON.stringify(data.tracks));
  }
  if (data.published) {
    columns += ',published'
    values.push(data.published);
  }
  if (discColor) {
    columns += ',disc_color'
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
      SELECT VinylPlays.id, Vinyls.album, Vinyls.artist, Vinyls.image_url, Vinyls.thumbnail_url, VinylPlays.side, VinylPlays.vinyl, VinylPlays.timestamp
      FROM VinylPlays INNER JOIN Vinyls
      ON VinylPlays.vinyl = Vinyls.id
      ORDER BY VinylPlays.timestamp DESC
    `
    const result = await executeQuery(query);
    res.status(200).send(result.map(p => ({
      playId: p.id,
      vinylId: p.vinyl,
      album: p.album,
      artist: p.artist,
      imageUrl: p.image_url,
      thumbnailUrl: p.thumbnail_url,
      side: p.side,
      timestamp: p.timestamp,
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

    res.status(200).send(vinylMap(vinyl));
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
    const vinyl = await getItemsById('Vinyls', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }
    
    let query = 'UPDATE Vinyls SET '
    const values = [];
    if (published) {
      query += 'published = ?, '
      values.push(published);
      vinyl.published = published;
    }
    if (nSides) {
      query += 'n_sides = ?, '
      values.push(nSides);
      vinyl.n_sides = nSides;
    }
    if (discColor) {
      query += 'disc_color = ?, '
      values.push(discColor);
      vinyl.disc_color = discColor;
    }
    if (values.length == 0) {
      return res.status(400).send('No data to update');
    }
    query = query.slice(0, query.length - 2);
    query += ' WHERE id = ?'
    values.push(id);
    await executeQuery(query, values);

    res.status(200).send(vinylMap(vinyl));
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

    const result = await getItems('VinylPlays', 'vinyl = ? ORDER BY timestamp DESC', [id]);
    res.status(200).send({
      album: vinyl.album,
      artist: vinyl.artist,
      plays: result.map(p => ({
        playId: p.id,
        side: p.side,
        timestamp: p.timestamp,
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
    date,
  } = req.body || {};
  let timestamp = '';
  if (date) {
    try {
      timestamp = new Date(date).toISOString().slice(0, 19).replace('T', ' ');
    } catch (e) {
      return res.status(400).send('Invalid Date String passed in');
    }
  }
  try {
    const vinyl = await getItemsById('Vinyls', id);
    if (!vinyl) {
      return res.status(404).send(`Vinyl ${id} not found`);
    }

    let columns = 'vinyl,side';
    if (timestamp) {
      columns += ',timestamp'
    }
    if (side) {
      await insertItem('VinylPlays', columns, timestamp ? [id, side, timestamp] : [id, side]);
    } else {
      const sideParams = [];
      for (let i = 0; i < vinyl.n_sides; i += 1) {
        sideParams.push(timestamp ? [id, i + 1, timestamp] : [id, i + 1]);
      }
      await executeQuery(`INSERT INTO VinylPlays (${columns}) VALUES ?`, [sideParams]);
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
