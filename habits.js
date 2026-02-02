import express from 'express';
const router = express.Router();

import bodyParser from 'body-parser';
const jsonParser = bodyParser.json();

import * as datastore from './datastore.js';

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
    const curDate = new Date();
    const year = curDate.getFullYear();
    const data = {
      userId: uid,
      name,
      description,
      frequency, // times per week
      color,
      checkInMasks: { [year]: getInitialCheckInMask(year), [year - 1]: getInitialCheckInMask(year - 1) },
      createdAt: curDate,
      updatedAt: curDate,
    }
    const id = await datastore.save('Habit', data);
    res.status(201).json({ message: `Habit ${id} created`, habit: { ...data, id } });
  } catch (err) {
    next(err);
  }
});

// Display all habits
router.get('/', async (req, res, next) => {
  const { uid } = req.user;

  try {
    const habits = await datastore.query('Habit', {
      property: 'userId', operator: '=', value: uid
    });
    const habitsObject = {};
    habits.forEach(habit => {
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
      habitsObject[habit.id] = habit;
    });

    res.status(200).send(habitsObject);
  } catch (err) {
    next(err)
  }
});

// Display habit by ID
router.get('/:id', async (req, res, next) => {
  const { id } = req.params;
  const { uid } = req.user;
  try {
    const habit = await datastore.get('Habit', id);
    if (!habit) {
      return res.status(404).send('Habit not found');
    }
    if (habit.userId !== uid) {
      return res.status(403).send('Forbidden: You do not have access to this habit');
    }

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
    const habit = await datastore.get('Habit', id);
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

    await datastore.update('Habit', id, habit);
    res.status(200).send({ message: `Habit ${id} updated`, habit });
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
    const habit = await datastore.get('Habit', id);
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

    await datastore.update('Habit', id, habit);
    res.status(200).send({ message: `Habit ${id} updated`, habit });
  } catch (err) {
    next(err);
  }
});

// Delete habit
router.delete('/:id', async (req, res, next) => {
  const { id } = req.params;
  const { uid } = req.user;

  try {
    const habit = await datastore.get('Habit', id);
    if (!habit) {
      return res.status(404).send('Habit not found');
    }
    if (habit.userId !== uid) {
      return res.status(403).send('Forbidden: You do not have access to this habit');
    }

    await datastore.del('Habit', id);
    res.status(204).send();
  } catch (err) {
    next(err)
  }
});

export default router;
