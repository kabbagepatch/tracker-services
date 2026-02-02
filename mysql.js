import mysql from 'mysql2/promise';
import {Connector} from '@google-cloud/cloud-sql-connector';

const connector = new Connector();
const createPool = async () => {
    const clientOpts = await connector.getOptions({
        instanceConnectionName: process.env.DB_INSTANCE,
        ipType: 'PUBLIC',
    });
    const pool = mysql.createPool({
        ...clientOpts,
        user: process.env.DB_USER,
        password: process.env.DB_PASS,
        database: process.env.DB_NAME,
    });

    console.log('Pool Created');
    return pool;
}
const poolPromise = createPool().catch(e => { console.log("Error creatinng mysql pool") });

export const closeConnection = async () => {
    const pool = await poolPromise;
    if (!pool) return;
    await pool.end();
    connector.close();
}

const getConnection = async () => {
    const pool = await poolPromise;
    if (!pool) return;
    return await pool.getConnection();
}

export const executeQuery = async (query, params) => {
    const conn = await getConnection();
    if (!conn) return;
    try {
        const [result] = await conn.query(query, params);

        return result;
    } catch (e) {
        console.log(e);
        throw new Error('There was an error with the SQL query');
    } finally {
        conn.release();
    }
}

export const executeQueries = async (queries) => {
    const conn = await getConnection();
    for (let q of queries) {
        await conn.query(q.query, q.params);
    }
    conn.release();
}

export const getItems = async (tableName, conditions, params, columns = '*') => {
    let query = `SELECT ${columns} FROM ${tableName}`;
    if (conditions) {
        query += ` WHERE ${conditions}`;
    }
    return await executeQuery(query, params);
}

export const getItemsById = async (tableName, id, columns = '*') => {
    let query = `SELECT ${columns} FROM ${tableName} WHERE id = ?`;

    return (await executeQuery(query, [id]))[0];
}

export const insertItem = async (tableName, columns, values) => {
    let query = `INSERT INTO ${tableName} (${columns}) VALUES (${values.map(_ => '?').join(',')})`;

    return await executeQuery(query, values);
}

export const removeItems = async (tableName, conditions = '', values) => {
    let query = `DELETE FROM ${tableName}`;
    if (conditions) {
        query += ` WHERE ${conditions}`;
    }

    return await executeQuery(query, values);
}

export const removeItem = async (tableName, id) => {
    let query = `DELETE FROM ${tableName} WHERE id = ?`;

    return await executeQuery(query, [id]);
}

