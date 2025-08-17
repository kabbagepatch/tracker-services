const {Datastore} = require('@google-cloud/datastore');
const datastore = new Datastore();

const express = require('express');
const router = express.Router();

const bodyParser = require('body-parser');
const jsonParser = bodyParser.json();

function getDayOfYear(date) {
  const start = Date.UTC(date.getFullYear(), 0, 0);
  const current = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const diff = current - start;
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function getInitialCheckInMask(year) {
  const isLeapYear = (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0);
  return "0".repeat(isLeapYear ? 366 : 365);
}

// Create habit
router.post('/', jsonParser, async (req, res, next) => {
  const {
    name,
    description,
    frequency,
    color,
  } = req.body || {};

  if (!name) {
    return res.status(400).send('Habit name is required');
  }

  const { uid } = req.user;

  try {
    const habitKey = datastore.key('Habit');
    const curDate = new Date();
    const year = curDate.getFullYear();
    const newHabit = {
      key: habitKey,
      data: {
        userId: uid,
        name,
        description,
        frequency, // times per week
        color,
        checkInMasks: { [year]: getInitialCheckInMask(year), [year - 1]: getInitialCheckInMask(year - 1) },
        createdAt: curDate,
        updatedAt: curDate,
      }
    }
    await datastore.save(newHabit);
    res.status(201).json({ message: `Habit ${habitKey.id} created`, habit: { ...newHabit.data, id: habitKey.id } });
  } catch (err) {
    next(err);
  }
});

// Display all habits
router.get('/', async (req, res, next) => {
  const { uid } = req.user;

  try {
    let query = datastore.createQuery('Habit');
    if (uid) {
      query = query.filter('userId', '=', uid)
    }
    const [habits] = await datastore.runQuery(query);
    const habitsObject = {};
    habits.forEach(habit => {
      habit.id = habit[datastore.KEY].id;
      habitsObject[habit.id] = habit;
      const year = new Date().getFullYear();
      if (!habit.checkInMasks) {
        habit.checkInMasks = {};
        habit.checkInMasks[year] = getInitialCheckInMask(year);
        habit.checkInMasks[year - 1] = getInitialCheckInMask(year - 1);
        habit.checkInMasks[year + 1] = getInitialCheckInMask(year + 1);
      }
      if (!habit.checkInMasks[year + 1]) {
        habit.checkInMasks[year + 1] = getInitialCheckInMask(year + 1);
      }
      if (!habit.checkInMasks[year]) {
        habit.checkInMasks[year] = getInitialCheckInMask(year);
      }
      if (!habit.checkInMasks[year - 1]) {
        habit.checkInMasks[year - 1] = getInitialCheckInMask(year - 1);
      }
      delete habit.checkIns;
      return habit;
    });
    res.status(200).send(habitsObject);
  } catch (err) {
    next(err)
  }
});

// Display habit by ID
router.get('/:id', async (req, res, next) => {
  const { id } = req.params;
  try {
    const habitKey = datastore.key(['Habit', datastore.int(id)]);
    const [habit] = await datastore.get(habitKey);
    const year = new Date().getFullYear();
    if (!habit.checkInMasks) {
      habit.checkInMasks = {};
      habit.checkInMasks[year] = getInitialCheckInMask(year);
      habit.checkInMasks[year - 1] = getInitialCheckInMask(year - 1);
      habit.checkInMasks[year + 1] = getInitialCheckInMask(year + 1);
    }
    if (!habit.checkInMasks[year + 1]) {
      habit.checkInMasks[year + 1] = getInitialCheckInMask(year + 1);
    }
    if (!habit.checkInMasks[year]) {
      habit.checkInMasks[year] = getInitialCheckInMask(year);
    }
    if (!habit.checkInMasks[year - 1]) {
      habit.checkInMasks[year - 1] = getInitialCheckInMask(year - 1);
    }
    delete habit.checkIns;
    res.status(200).send({ habit });
  } catch (err) {
    next(err)
  }
});

// Update habit
router.put('/:id', jsonParser, async (req, res, next) => {
  const { id } = req.params;
  const {
    name,
    description,
    frequency,
    color,
  } = req.body;
  const { uid } = req.user;

  if (name !== undefined && name.trim() === '') {
    return res.status(400).send('Habit name is required');
  }

  try {
    const habitKey = datastore.key(['Habit', datastore.int(id)]);
    const [habit] = await datastore.get(habitKey);
    if (!habit) {
      return res.status(404).send('Habit not found');
    }
    if (habit.userId !== uid) {
      return res.status(403).send('Forbidden: You do not have access to this habit');
    }

    habit.name = name || habit.name;
    habit.description = description || habit.description;
    habit.color = color || habit.color;
    habit.frequency = frequency || habit.frequency;
    habit.updatedAt = new Date();

    await datastore.save({ key: habitKey, data: habit });
    res.status(200).send({ message: `Habit ${habitKey.id} updated`, habit });
  } catch (err) {
    next(err);
  }
});

router.post('/:id/check-in', jsonParser, async (req, res, next) => {
  const { id } = req.params;
  const {
    date: dateString,
    status,
  } = req.body;
  const { uid } = req.user;

  try {
    const habitKey = datastore.key(['Habit', datastore.int(id)]);
    const [habit] = await datastore.get(habitKey);
    if (!habit) {
      return res.status(404).send('Habit not found');
    }
    if (habit.userId !== uid) {
      return res.status(403).send('Forbidden: You do not have access to this habit');
    }

    const date = new Date(dateString);
    const year = date.getFullYear();
    if (!habit.checkInMasks) {
      habit.checkInMasks = {};
    }
    let checkInsMask = habit.checkInMasks[year] || getInitialCheckInMask(year);
    const dayOfYear = getDayOfYear(date);
    checkInsMask = checkInsMask.substring(0, dayOfYear - 1) + (status ? '1' : '0') + checkInsMask.substring(dayOfYear);
    habit.checkInMasks[year] = checkInsMask;

    await datastore.save({ key: habitKey, data: habit });
    res.status(200).send({ message: `Habit ${habitKey.id} updated`, habit });
  } catch (err) {
    next(err);
  }
});

// Delete habit
router.delete('/:id', async (req, res, next) => {
  const { id } = req.params;
  try {
    const habitKey = datastore.key(['Habit', datastore.int(id)]);
    const [habit] = await datastore.get(habitKey);
    if (!habit) {
      return res.status(404).send('Habit not found');
    }

    await datastore.delete(habitKey);
    res.status(200).send('Habit deleted succesfully');
  } catch (err) {
    next(err)
  }
});

module.exports = router;
