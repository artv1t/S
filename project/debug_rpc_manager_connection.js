import { Connection } from '@solana/web3.js';
import { RPCManager } from './src/rpc/rpcManager.js';
import { config } from './src/config/index.js';

async function debugRPCManagerConnection() {
  console.log('🔍 Comparing RPC Manager connection vs Direct connection...\n');
  
  // Test 1: Direct connection (what worked in my test)
  console.log('📊 Test 1: Direct connection (known working)');
  const directConnection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  try {
    const directSlot = await directConnection.getSlot();
    console.log(`✅ Direct connection: slot ${directSlot}`);
  } catch (error) {
    console.log(`❌ Direct connection failed: ${error.message}`);
  }
  
  // Test 2: RPC Manager connection (what bot uses)
  console.log('\n📊 Test 2: RPC Manager connection (what bot uses)');
  const rpcManager = new RPCManager();
  
  // Wait a moment for RPC manager to initialize
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  const managedConnection = rpcManager.getHealthyConnection();
  
  if (!managedConnection) {
    console.log('❌ RPC Manager returned null connection!');
    console.log('Health status:', rpcManager.getHealthStatus());
    return;
  }
  
  console.log('✅ RPC Manager provided connection');
  
  try {
    const managedSlot = await managedConnection.getSlot();
    console.log(`✅ RPC Manager connection: slot ${managedSlot}`);
  } catch (error) {
    console.log(`❌ RPC Manager connection failed: ${error.message}`);
    console.log(`Error type: ${error.constructor.name}`);
    console.log(`Stack: ${error.stack?.split('\n')[0]}`);
  }
  
  // Test 3: Try the exact bot token discovery logic with RPC manager connection
  console.log('\n📊 Test 3: Bot token discovery logic with RPC Manager connection');
  
  try {
    const slot = await managedConnection.getSlot();
    const recentSlots = Array.from({ length: 1 }, (_, i) => slot - i); // Just test 1 slot
    
    for (const slotNumber of recentSlots) {
      console.log(`  🔍 Testing slot ${slotNumber} with RPC Manager connection...`);
      try {
        const block = await managedConnection.getBlock(slotNumber, {
          commitment: 'confirmed',
          maxSupportedTransactionVersion: 0
        });
        
        if (block && block.transactions) {
          console.log(`    ✅ Block loaded: ${block.transactions.length} transactions`);
        } else {
          console.log(`    ⚠️ Block has no data`);
        }
        
      } catch (blockError) {
        console.log(`    ❌ BLOCK ERROR (this is likely the bot error!): ${blockError.message}`);
        console.log(`    Error type: ${blockError.constructor.name}`);
        console.log(`    Stack: ${blockError.stack?.split('\n')[0]}`);
        
        // This is probably the exact error the bot is seeing
        break;
      }
    }
    
  } catch (mainError) {
    console.log(`\n❌ MAIN ERROR (this matches bot "Error getting recent token mints:"):`);
    console.log(`   Message: ${mainError.message}`);
    console.log(`   Type: ${mainError.constructor.name}`);
    console.log(`   Stack: ${mainError.stack?.split('\n').slice(0, 3).join('\n')}`);
  }
  
  // Test 4: Check RPC Manager health status
  console.log('\n📊 Test 4: RPC Manager health status');
  const healthStatus = rpcManager.getHealthStatus();
  console.log('RPC Health Status:');
  healthStatus.forEach((health, index) => {
    console.log(`  RPC ${index + 1}: ${health.healthy ? '✅' : '❌'} ${health.latency}ms (errors: ${health.errorCount})`);
  });
  
  console.log(`\nAverage latency: ${rpcManager.getAverageLatency()}ms`);
  console.log(`Total requests: ${rpcManager.getTotalRequests()}`);
  
  // Cleanup
  rpcManager.destroy();
}

debugRPCManagerConnection().catch(console.error);
