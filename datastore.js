import { Datastore } from '@google-cloud/datastore';
const datastore = new Datastore();

export const save = async (keyName, data) => {
  const key = datastore.key(keyName);
  await datastore.save({ key, data });

  return key.id;
};

export const query = async (keyName, filter, order) => {
  let query = datastore.createQuery(keyName);
  if (filter) {
    query = query.filter(filter.property, filter.operator, filter.value);
  }
  if (order) {
    query = query.order(order.name, {
      descending: order.descending,
    })
  }

  const [result] = await datastore.runQuery(query);
  return result.map(item => ({
    id: item[datastore.KEY].id,
    ...item,
  }));
};

export const get = async (keyName, id) => {
  const key = datastore.key([keyName, datastore.int(id)]);
  const [result] = await datastore.get(key);
  result.id = result[datastore.KEY].id;

  return result;
}

export const getMultiple = async (keyName, ids) => {
  const keys = ids.map(id => datastore.key([keyName, datastore.int(id)]));
  const [result] = await datastore.get(keys);
  result.forEach(r => {
    r.id = r[datastore.KEY].id;
  });

  return result;
}

export const update = async (keyName, id, data) => {
  const key = datastore.key([keyName, datastore.int(id)]);
  delete data.id;
  await datastore.save({ key, data });

  return key.id;
}

export const del = async (keyName, id) => {
  const key = datastore.key([keyName, datastore.int(id)]);
  await datastore.delete(key);
}
