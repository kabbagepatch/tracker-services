import express from 'express';
const router = express.Router();

import bodyParser from 'body-parser';
const jsonParser = bodyParser.json();

import { executeQueries, executeQuery, getItems, getItemsById, insertItem, removeItem, removeItems } from "./mysql.js"

export const initializeDatabase = async () => {
  await executeQuery(`
    CREATE TABLE IF NOT EXISTS Vinyls (
      id INT AUTO_INCREMENT PRIMARY KEY,
      album_name VARCHAR(255) NOT NULL,
      artist_name VARCHAR(255) NOT NULL,
      disc_hex VARCHAR(255) DEFAULT "#000",
      n_sides INT NOT NULL DEFAULT 2,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);

  await executeQuery(`
    CREATE TABLE IF NOT EXISTS Songs (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(255) NOT NULL,
      vinyl INT NOT NULL,
      side INT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT FK_VinylSongs FOREIGN KEY (vinyl)
      REFERENCES Vinyls(id)
    )
  `);

  await executeQuery(`
    CREATE TABLE IF NOT EXISTS SidePlays (
      id INT AUTO_INCREMENT PRIMARY KEY,
      vinyl INT NOT NULL,
      side INT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT FK_VinylSide FOREIGN KEY (vinyl)
      REFERENCES Vinyls(id)
    )
  `);
}

router.get('/', async (req, res, next) => {
  try {
    const vinyls = await getItems('Vinyls')
    res.status(200).send(vinyls.map(v => ({
      id: v.id,
      album: v.album_name,
      artist: v.artist_name,
      discColor: v.disc_hex,
      nSides: v.n_sides,
    })));
  } catch (err) {
    next(err);
  }
});

const insertSongs = async (sides, vinyl) => {
  const songParams = []
  let query = `
    INSERT INTO Songs (name, vinyl, side) 
    VALUES ?
  `;
  for (let [side, songs] of sides.entries()) {
    for (let song of songs) {
      songParams.push([song, vinyl, side + 1]);
    }
  }
  await executeQuery(query, [songParams]);
}

router.post('/', jsonParser, async (req, res, next) => {
  const {
    album,
    artist,
    sides,
    nSides,
    discColor,
  } = req.body || {};

  if (!album) return res.status(400).send('Album name is required');
  if (!artist) return res.status(400).send('Artist name is required');

  let columns = 'album_name,artist_name';
  const values = [album, artist];
  if (discColor) {
    columns += ',disc_hex'
    values.push(discColor);
  }
  if (sides || nSides) {
    columns += ',n_sides'
    values.push(nSides || sides.length);
  }

  try {
    const result = await insertItem('Vinyls', columns, values);
    if (sides) {
      await insertSongs(sides, result.insertId);
    }
    res.status(201).send({ id: result.insertId, ...req.body });
  } catch (err) {
    next(err);
  }
});

router.get('/history', jsonParser, async (req, res, next) => {
  try {
    const query = `
      SELECT Vinyls.album_name, Vinyls.artist_name, SidePlays.id, SidePlays.side, SidePlays.created_at
      FROM SidePlays INNER JOIN Vinyls
      ON SidePlays.vinyl = Vinyls.id
    `
    const result = await executeQuery(query);
    res.status(200).send(result.map(p => ({
      playId: p.id,
      album: p.album_name,
      artist: p.artist_name,
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
    const songs = await getItems('Songs', `vinyl = ?`, [id])
    res.status(200).send({
      id: vinyl.id,
      album: vinyl.album_name,
      artist: vinyl.artist_name,
      discColor: vinyl.disc_hex,
      nSides: vinyl.n_sides,
      songs: songs.map(s => ({
        name: s.name,
        side: s.side,
      })),
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

    await removeItems('Songs', `vinyl = ${id}`)
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

    const result = await getItems('SidePlays', 'vinyl = ?', [id]);
    res.status(200).send({
      album: vinyl.album_name,
      artist: vinyl.artist_name,
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

    await insertItem('SidePlays', 'vinyl,side', [id, side]);
    res.status(201).send();
  } catch (err) {
    next(err);
  }
});

router.delete('/:id/plays/:playId', jsonParser, async (req, res, next) => {
  const { playId } = req.params;
  try {
    await removeItem('SidePlays', playId);
    res.status(204).send();
  } catch (err) {
    next(err);
  }
});

export default router;

// initializeDatabase();
