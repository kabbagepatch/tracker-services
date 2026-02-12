import express from 'express';
const router = express.Router();

router.get('/lastfm/search', async (req, res, next) => {
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

export const getAlbumLastFM = async (artist, album) => {
  try {
    const url = `https://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key=${process.env.LAST_FM_API_KEY}&artist=${artist}&album=${album}&format=json`;
    const result = await fetch(url);
    const data = await result.json();

    return {
      album: data.album.name,
      artist: data.album.artist,
      imageUrl: data.album.image[data.album.image.length - 1]['#text'],
      thumbnailUrl: data.album.image[1]['#text'],
    }
  } catch (e) {
    console.log(e.message);
  }
}

router.get('/lastfm', async (req, res, next) => {
  const album = req.query.album;
  const artist = req.query.artist;
  if (!album || !artist) {
    return res.status(400).send('Album and Artist required')
  }

  const data = await getAlbumLastFM(artist, album);
  res.status(200).send(data);
});

router.get('/discogs/search', async (req, res, next) => {
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
    barcode: v.barcode[0],
  })));
});

export const getAlbumDiscogs = async (discogsId) => {
  if (!discogsId) return;

  try {
    const url = `https://api.discogs.com/releases/${discogsId}`;
    const result = await fetch(url);
    const data = await result.json();
    const tracks = data.tracklist.map(t => ({ position: t.position, title: t.title }));

    return {
      album: data.title,
      artist: data.artists[0].name,
      genres: data.genres,
      imageUrl: data.images[0].uri,
      published: data.year,
      nSides: tracks[tracks.length - 1].position.charCodeAt(0) - 'A'.charCodeAt(0) + 1,
      discColor: data.formats?.length && data.formats[0].text ? data.formats[0].text : 'Black',
      tracks,
    }
  } catch (e) {
    console.log(e.message);
  }
}

router.get('/discogs/:id', async (req, res) => {
  const { id } = req.params;
  const data = await getAlbumDiscogs(id);
  res.status(200).send(data);
});

export default router;
